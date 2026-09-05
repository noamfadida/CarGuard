from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .models import UserProfile

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    chat_id INTEGER PRIMARY KEY,
    keywords TEXT NOT NULL DEFAULT '[]',
    location TEXT NOT NULL DEFAULT '',
    profile_text TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sent_jobs (
    chat_id INTEGER NOT NULL,
    job_uid TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    PRIMARY KEY (chat_id, job_uid)
);
"""


class Storage:
    """Thin SQLite persistence layer.

    Every public method is async and runs the actual (blocking) sqlite3
    call in a worker thread via asyncio.to_thread, so it's safe to call
    from the bot's event loop without stalling it. A fresh connection is
    opened per call rather than shared across threads/coroutines - simple
    and plenty fast for a single-bot polling workload.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> UserProfile:
        return UserProfile(
            chat_id=row["chat_id"],
            keywords=json.loads(row["keywords"]),
            location=row["location"],
            profile_text=row["profile_text"],
            active=bool(row["active"]),
        )

    def _get_user_sync(self, chat_id: int) -> Optional[UserProfile]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
            return self._row_to_user(row) if row is not None else None

    def _upsert_user_sync(self, user: UserProfile) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO users (chat_id, keywords, location, profile_text, active, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    keywords=excluded.keywords,
                    location=excluded.location,
                    profile_text=excluded.profile_text,
                    active=excluded.active
                """,
                (
                    user.chat_id,
                    json.dumps(user.keywords),
                    user.location,
                    user.profile_text,
                    int(user.active),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def _get_active_users_sync(self) -> List[UserProfile]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM users WHERE active = 1").fetchall()
            return [self._row_to_user(r) for r in rows]

    def _has_sent_sync(self, chat_id: int, job_uid: str) -> bool:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT 1 FROM sent_jobs WHERE chat_id = ? AND job_uid = ?",
                (chat_id, job_uid),
            ).fetchone()
            return row is not None

    def _mark_sent_sync(self, chat_id: int, job_uid: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sent_jobs (chat_id, job_uid, sent_at) VALUES (?, ?, ?)",
                (chat_id, job_uid, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    async def get_user(self, chat_id: int) -> Optional[UserProfile]:
        return await asyncio.to_thread(self._get_user_sync, chat_id)

    async def upsert_user(self, user: UserProfile) -> None:
        await asyncio.to_thread(self._upsert_user_sync, user)

    async def get_active_users(self) -> List[UserProfile]:
        return await asyncio.to_thread(self._get_active_users_sync)

    async def has_sent(self, chat_id: int, job_uid: str) -> bool:
        return await asyncio.to_thread(self._has_sent_sync, chat_id, job_uid)

    async def mark_sent(self, chat_id: int, job_uid: str) -> None:
        await asyncio.to_thread(self._mark_sent_sync, chat_id, job_uid)
