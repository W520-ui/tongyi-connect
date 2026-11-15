"""Legacy archive access with SQL aggregates and persisted failures."""

import json
import sqlite3
import threading
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.types import WorkflowResult


class WorkflowArchive:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS workflow_conversations (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, session_id TEXT NOT NULL,
                message TEXT NOT NULL, reply TEXT NOT NULL, merchant_summary TEXT NOT NULL,
                intent TEXT NOT NULL, intent_label TEXT NOT NULL, detected_intents TEXT NOT NULL,
                product_id TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL, language_label TEXT NOT NULL,
                needs_human INTEGER NOT NULL, human_acknowledged INTEGER NOT NULL DEFAULT 0,
                handoff_reason TEXT, issue_summary TEXT, is_command INTEGER NOT NULL DEFAULT 0,
                handoff_created INTEGER NOT NULL DEFAULT 0, tool_trace TEXT NOT NULL DEFAULT '{}'
            )
        """)
        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(workflow_conversations)")
        }
        for name, declaration in (
            ("product_id", "TEXT NOT NULL DEFAULT ''"),
            ("human_acknowledged", "INTEGER NOT NULL DEFAULT 0"),
            ("handoff_reason", "TEXT"),
            ("issue_summary", "TEXT"),
            ("is_command", "INTEGER NOT NULL DEFAULT 0"),
            ("handoff_created", "INTEGER NOT NULL DEFAULT 0"),
            ("tool_trace", "TEXT NOT NULL DEFAULT '{}'"),
        ):
            if name not in columns:
                self.connection.execute(
                    f"ALTER TABLE workflow_conversations ADD COLUMN {name} {declaration}"
                )
                if name == "handoff_created":
                    self.connection.execute(
                        "UPDATE workflow_conversations SET handoff_created=needs_human"
                    )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_created_at "
            "ON workflow_conversations(created_at DESC)"
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_session ON workflow_conversations(session_id)"
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_pending "
            "ON workflow_conversations(handoff_created, human_acknowledged)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS workflow_failures "
            "(id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, error_code TEXT NOT NULL)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS workflow_metadata "
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        self.connection.execute(
            "INSERT OR IGNORE INTO workflow_metadata VALUES ('started_at', ?)",
            (datetime.now(UTC).isoformat(),),
        )
        self.connection.commit()

    def existing_handoff(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                """
                SELECT * FROM workflow_conversations WHERE session_id=? AND handoff_created=1
                    AND human_acknowledged=0 ORDER BY created_at DESC LIMIT 1
            """,
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def append(self, message: str, result: WorkflowResult, *, is_command: bool = False) -> str:
        from app.domain.types import INTENT_LABELS, LANGUAGE_LABELS

        with self._lock:
            existing = self.existing_handoff(result.session_id)
            handoff_created = result.needs_human and existing is None
            record_id = str(uuid4())
            self.connection.execute(
                """
                INSERT INTO workflow_conversations
                    (id, created_at, session_id, message, reply, merchant_summary, intent,
                     intent_label, detected_intents, product_id, language, language_label,
                     needs_human, human_acknowledged, handoff_reason, issue_summary, is_command,
                     handoff_created, tool_trace)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record_id,
                    datetime.now(UTC).isoformat(),
                    result.session_id,
                    message.strip()[:180],
                    result.reply[:240],
                    result.merchant_summary[:240],
                    result.analysis.intent,
                    INTENT_LABELS[result.analysis.intent],
                    json.dumps(result.analysis.intents),
                    result.products[0].id if result.products else "",
                    result.analysis.language,
                    LANGUAGE_LABELS[result.analysis.language],
                    int(result.needs_human),
                    0,
                    result.handoff_reason,
                    result.issue_summary,
                    int(is_command),
                    int(handoff_created),
                    json.dumps(asdict(result.trace), ensure_ascii=False),
                ),
            )
            self.connection.commit()
        return existing["id"] if is_command and existing else record_id

    def recent(self, limit: int = 8) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM workflow_conversations WHERE is_command=0 "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def handoffs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM workflow_conversations "
                "WHERE handoff_created=1 AND human_acknowledged=0 "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def acknowledge(self, record_id: str) -> bool:
        with self._lock:
            cursor = self.connection.execute(
                "UPDATE workflow_conversations SET human_acknowledged=1 "
                "WHERE id=? AND handoff_created=1 AND human_acknowledged=0",
                (record_id,),
            )
            self.connection.commit()
            return cursor.rowcount == 1

    def record_failure(self, code: str) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT INTO workflow_failures(created_at, error_code) VALUES (?, ?)",
                (datetime.now(UTC).isoformat(), code),
            )
            self.connection.commit()

    def aggregates(self) -> dict[str, Any]:
        with self._lock, self.connection:
            self.connection.execute("BEGIN")
            total = self.connection.execute(
                "SELECT COUNT(*) FROM workflow_conversations WHERE is_command=0"
            ).fetchone()[0]
            handoffs = self.connection.execute(
                "SELECT COALESCE(SUM(handoff_created), 0) FROM workflow_conversations"
            ).fetchone()[0]
            pending = self.connection.execute(
                "SELECT COUNT(*) FROM workflow_conversations "
                "WHERE handoff_created=1 AND human_acknowledged=0"
            ).fetchone()[0]
            failures = self.connection.execute("SELECT COUNT(*) FROM workflow_failures").fetchone()[
                0
            ]
            languages = self.connection.execute(
                "SELECT language AS code, COUNT(*) AS count FROM workflow_conversations "
                "WHERE is_command=0 GROUP BY language ORDER BY count DESC, language"
            ).fetchall()
            intents = self.connection.execute("""
                SELECT value AS code, COUNT(*) AS count FROM (
                    SELECT DISTINCT records.id, terms.value FROM workflow_conversations AS records,
                        json_each(CASE WHEN json_valid(detected_intents)
                            THEN detected_intents ELSE json_array(intent) END) AS terms
                    WHERE is_command=0
                ) GROUP BY value ORDER BY count DESC, value
            """).fetchall()
            started_at = self.connection.execute(
                "SELECT value FROM workflow_metadata WHERE key='started_at'"
            ).fetchone()[0]
        return {
            "total": total,
            "handoffs": handoffs,
            "pending": pending,
            "failures": failures,
            "languages": [dict(row) for row in languages],
            "intents": [dict(row) for row in intents],
            "started_at": started_at,
        }

    def ping(self) -> bool:
        try:
            with self._lock:
                return self.connection.execute("SELECT 1").fetchone()[0] == 1
        except sqlite3.Error:
            return False

    def close(self) -> None:
        self.connection.close()
