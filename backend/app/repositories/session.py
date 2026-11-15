"""Temporary legacy JSON session storage; replaced by append-only tables in phase 2."""

import json
import sqlite3
import threading
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.domain.types import Session, Turn


class SessionStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS agent_sessions (
                session_id TEXT PRIMARY KEY, turns TEXT NOT NULL DEFAULT '[]',
                last_product_id TEXT NOT NULL DEFAULT '', language TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL, reply_language TEXT,
                focused_product_ids TEXT NOT NULL DEFAULT '[]', destination_country TEXT,
                quantity INTEGER
            )
        """)
        columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(agent_sessions)")
        }
        for name, declaration in (
            ("reply_language", "TEXT"),
            ("focused_product_ids", "TEXT NOT NULL DEFAULT '[]'"),
            ("destination_country", "TEXT"),
            ("quantity", "INTEGER"),
        ):
            if name not in columns:
                self.connection.execute(
                    f"ALTER TABLE agent_sessions ADD COLUMN {name} {declaration}"
                )
        self.connection.commit()

    def load(self, session_id: str, ttl_hours: int = 24) -> Session:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM agent_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        if row is None:
            return Session(session_id)
        if datetime.now(UTC) - datetime.fromisoformat(row["updated_at"]) > timedelta(
            hours=ttl_hours
        ):
            self.clear(session_id)
            return Session(session_id)
        try:
            turns = [
                Turn(**{**item, "tool_calls": tuple(item.get("tool_calls") or ())})
                for item in json.loads(row["turns"])
            ]
        except (TypeError, ValueError, AttributeError):
            turns = []
        try:
            focused_data = json.loads(row["focused_product_ids"])
            if not isinstance(focused_data, list) or any(
                not isinstance(item, str) for item in focused_data
            ):
                raise ValueError("Invalid product focus")
            focused = tuple(focused_data)
        except (TypeError, ValueError):
            focused = ()
        if not focused and row["last_product_id"]:
            focused = (row["last_product_id"],)
        return Session(
            session_id=session_id,
            turns=turns,
            focused_product_ids=focused,
            reply_language=row["reply_language"] or None,
            detected_language=row["language"] or None,
            destination_country=row["destination_country"],
            quantity=row["quantity"],
            updated_at=row["updated_at"],
        )

    def save(self, session: Session) -> None:
        session.updated_at = datetime.now(UTC).isoformat()
        with self._lock:
            self.connection.execute(
                """
                INSERT INTO agent_sessions
                    (session_id, turns, last_product_id, language, updated_at, reply_language,
                     focused_product_ids, destination_country, quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET turns=excluded.turns,
                    last_product_id=excluded.last_product_id, language=excluded.language,
                    updated_at=excluded.updated_at, reply_language=excluded.reply_language,
                    focused_product_ids=excluded.focused_product_ids,
                    destination_country=excluded.destination_country, quantity=excluded.quantity
            """,
                (
                    session.session_id,
                    json.dumps([asdict(turn) for turn in session.turns], ensure_ascii=False),
                    session.last_product_id or "",
                    session.detected_language or "",
                    session.updated_at,
                    session.reply_language,
                    json.dumps(session.focused_product_ids),
                    session.destination_country,
                    session.quantity,
                ),
            )
            self.connection.commit()

    def append(self, session: Session, turn: Turn) -> None:
        session.turns.append(turn)
        self.save(session)

    def clear(self, session_id: str) -> None:
        with self._lock:
            self.connection.execute(
                "DELETE FROM agent_sessions WHERE session_id = ?", (session_id,)
            )
            self.connection.commit()

    def close(self) -> None:
        self.connection.close()
