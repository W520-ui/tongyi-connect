from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import threading

from app.agent.models import Session, Turn


class SessionStore:
    """Persist multi-turn context next to the existing workflow archive."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path(__file__).resolve().parents[2] / "data" / "workflow.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_sessions (
                session_id TEXT PRIMARY KEY,
                turns TEXT NOT NULL DEFAULT '[]',
                last_product_id TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    def load(self, session_id: str, ttl_hours: int = 24) -> Session:
        key = session_id[:120]
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM agent_sessions WHERE session_id = ?", (key,)
            ).fetchone()
        if row is None:
            return Session(session_id=key)

        updated = datetime.fromisoformat(row["updated_at"])
        if datetime.now(timezone.utc) - updated > timedelta(hours=ttl_hours):
            self.clear(key)
            return Session(session_id=key)

        try:
            turns = [Turn(**item) for item in json.loads(row["turns"])]
        except (TypeError, ValueError, json.JSONDecodeError):
            turns = []
        return Session(
            session_id=row["session_id"],
            turns=turns,
            last_product_id=row["last_product_id"] or None,
            language=row["language"] or None,
            updated_at=row["updated_at"],
        )

    def append(self, session: Session, turn: Turn) -> None:
        session.turns.append(turn)
        del session.turns[:-50]
        session.updated_at = datetime.now(timezone.utc).isoformat()
        serialized = json.dumps(
            [
                {"role": item.role, "content": item.content, "created_at": item.created_at}
                for item in session.turns
            ],
            ensure_ascii=False,
        )
        with self._lock:
            self.connection.execute(
                """
                INSERT INTO agent_sessions
                    (session_id, turns, last_product_id, language, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    turns = excluded.turns,
                    last_product_id = excluded.last_product_id,
                    language = excluded.language,
                    updated_at = excluded.updated_at
                """,
                (
                    session.session_id,
                    serialized,
                    session.last_product_id or "",
                    session.language or "",
                    session.updated_at,
                ),
            )
            self.connection.commit()

    def clear(self, session_id: str) -> None:
        with self._lock:
            self.connection.execute(
                "DELETE FROM agent_sessions WHERE session_id = ?", (session_id[:120],)
            )
            self.connection.commit()

    def close(self) -> None:
        with self._lock:
            self.connection.close()
