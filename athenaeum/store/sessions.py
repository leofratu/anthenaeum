from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from athenaeum.schemas import SessionRecord, utc_now


class SessionStore:
    def __init__(self, path: Path = Path(".thinktank") / "sessions.sqlite3"):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                  id TEXT PRIMARY KEY,
                  question TEXT NOT NULL,
                  status TEXT NOT NULL,
                  daily_budget REAL NOT NULL,
                  duration TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  last_wake_at TEXT,
                  data_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wake_queue (
                  id TEXT PRIMARY KEY,
                  session_id TEXT NOT NULL,
                  reason TEXT NOT NULL,
                  requested_at TEXT NOT NULL,
                  consumed_at TEXT,
                  payload_json TEXT NOT NULL
                )
                """
            )

    def create(self, session: SessionRecord) -> None:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session.id, session.question, session.status, session.daily_budget, session.duration, session.created_at, now, session.last_wake_at, json.dumps(session.model_dump(mode="json"), sort_keys=True)),
            )
            self.enqueue_wake(session.id, "manual", {"initial": True}, conn=conn)

    def list(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute("SELECT id, question, status, daily_budget, duration, created_at, last_wake_at FROM sessions ORDER BY created_at")]

    def get(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    def set_status(self, session_id: str, status: str) -> None:
        with self._connect() as conn:
            changed = conn.execute("UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?", (status, utc_now(), session_id)).rowcount
        if not changed:
            raise KeyError(session_id)

    def enqueue_wake(self, session_id: str, reason: str, payload: dict[str, Any] | None = None, conn=None) -> str:
        wake_id = f"wake-{session_id}-{utc_now()}-{reason}"
        owns = conn is None
        conn = conn or self._connect()
        try:
            conn.execute(
                "INSERT INTO wake_queue VALUES (?, ?, ?, ?, ?, ?)",
                (wake_id, session_id, reason, utc_now(), None, json.dumps(payload or {}, sort_keys=True)),
            )
        finally:
            if owns:
                conn.commit()
                conn.close()
        return wake_id

    def due_wakes(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT wake_queue.*
                    FROM wake_queue
                    JOIN sessions ON sessions.id = wake_queue.session_id
                    WHERE wake_queue.consumed_at IS NULL
                      AND sessions.status = 'running'
                    ORDER BY wake_queue.requested_at
                    """
                )
            ]

    def consume_wake(self, wake_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE wake_queue SET consumed_at = ? WHERE id = ?", (utc_now(), wake_id))
