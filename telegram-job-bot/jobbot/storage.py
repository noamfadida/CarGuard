from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .models import Job, UserProfile

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    chat_id INTEGER PRIMARY KEY,
    keywords TEXT NOT NULL DEFAULT '[]',
    location TEXT NOT NULL DEFAULT '',
    profile_text TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    persona TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sent_jobs (
    chat_id INTEGER NOT NULL,
    job_uid TEXT NOT NULL,
    token TEXT,
    title TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    sent_at TEXT NOT NULL,
    PRIMARY KEY (chat_id, job_uid)
);

CREATE INDEX IF NOT EXISTS idx_sent_jobs_token ON sent_jobs(token);

-- One row per (chat, job): a later vote on the same job overwrites the
-- earlier one rather than creating a second row.
CREATE TABLE IF NOT EXISTS job_feedback (
    chat_id INTEGER NOT NULL,
    job_uid TEXT NOT NULL,
    vote TEXT NOT NULL,
    created_at TEXT NOT NULL,
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
            self._migrate(conn)
            conn.commit()

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Add columns introduced after a db file may already exist on disk.

        SCHEMA's CREATE TABLE already has these for a fresh db; this only
        matters for a sent_jobs table created before the feedback feature
        existed.
        """
        existing = {row[1] for row in conn.execute("PRAGMA table_info(sent_jobs)")}
        for column, ddl in (
            ("token", "ALTER TABLE sent_jobs ADD COLUMN token TEXT"),
            ("title", "ALTER TABLE sent_jobs ADD COLUMN title TEXT NOT NULL DEFAULT ''"),
            ("company", "ALTER TABLE sent_jobs ADD COLUMN company TEXT NOT NULL DEFAULT ''"),
            ("location", "ALTER TABLE sent_jobs ADD COLUMN location TEXT NOT NULL DEFAULT ''"),
        ):
            if column not in existing:
                conn.execute(ddl)

        existing_users = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "persona" not in existing_users:
            conn.execute("ALTER TABLE users ADD COLUMN persona TEXT NOT NULL DEFAULT ''")

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
            persona=row["persona"] if "persona" in row.keys() else "",
        )

    def _get_user_sync(self, chat_id: int) -> Optional[UserProfile]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
            return self._row_to_user(row) if row is not None else None

    def _upsert_user_sync(self, user: UserProfile) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO users (chat_id, keywords, location, profile_text, active, persona, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    keywords=excluded.keywords,
                    location=excluded.location,
                    profile_text=excluded.profile_text,
                    active=excluded.active,
                    persona=excluded.persona
                """,
                (
                    user.chat_id,
                    json.dumps(user.keywords),
                    user.location,
                    user.profile_text,
                    int(user.active),
                    user.persona,
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

    def _mark_sent_sync(self, chat_id: int, job: Job, token: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO sent_jobs (chat_id, job_uid, token, title, company, location, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    job.uid,
                    token,
                    job.title,
                    job.company,
                    job.location,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def _get_sent_job_sync(self, chat_id: int, token: str) -> Optional[dict]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT job_uid, title, company, location FROM sent_jobs WHERE chat_id = ? AND token = ?",
                (chat_id, token),
            ).fetchone()
            return dict(row) if row is not None else None

    def _record_feedback_sync(self, chat_id: int, job_uid: str, vote: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO job_feedback (chat_id, job_uid, vote, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id, job_uid) DO UPDATE SET
                    vote = excluded.vote,
                    created_at = excluded.created_at
                """,
                (chat_id, job_uid, vote, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def _get_recent_feedback_sync(self, chat_id: int, limit: int) -> List[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT f.vote AS vote, s.title AS title, s.company AS company
                FROM job_feedback f
                JOIN sent_jobs s ON s.chat_id = f.chat_id AND s.job_uid = f.job_uid
                WHERE f.chat_id = ?
                ORDER BY f.created_at DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def _get_persona_stats_sync(self) -> List[dict]:
        """Per persona variant: how many users got it, how many activated.

        "Activated" here mirrors the design doc's definition - set at
        least one filter or a profile - as a cheap proxy for engagement
        while a small A/B group is still too little data for anything
        more rigorous (real retention, application click-throughs, etc).
        """
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT
                    persona,
                    COUNT(*) AS total,
                    SUM(
                        CASE WHEN keywords != '[]' OR location != '' OR profile_text != ''
                        THEN 1 ELSE 0 END
                    ) AS activated
                FROM users
                GROUP BY persona
                ORDER BY persona
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def _get_feedback_counts_sync(self, chat_id: int) -> tuple[int, int]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN vote = 'up' THEN 1 ELSE 0 END) AS ups,
                    SUM(CASE WHEN vote = 'down' THEN 1 ELSE 0 END) AS downs
                FROM job_feedback
                WHERE chat_id = ?
                """,
                (chat_id,),
            ).fetchone()
            return (row["ups"] or 0, row["downs"] or 0)

    async def get_user(self, chat_id: int) -> Optional[UserProfile]:
        return await asyncio.to_thread(self._get_user_sync, chat_id)

    async def upsert_user(self, user: UserProfile) -> None:
        await asyncio.to_thread(self._upsert_user_sync, user)

    async def get_active_users(self) -> List[UserProfile]:
        return await asyncio.to_thread(self._get_active_users_sync)

    async def has_sent(self, chat_id: int, job_uid: str) -> bool:
        return await asyncio.to_thread(self._has_sent_sync, chat_id, job_uid)

    async def mark_sent(self, chat_id: int, job: Job, token: str) -> None:
        await asyncio.to_thread(self._mark_sent_sync, chat_id, job, token)

    async def get_sent_job(self, chat_id: int, token: str) -> Optional[dict]:
        """Resolve a feedback-button token back to the job it was sent for."""
        return await asyncio.to_thread(self._get_sent_job_sync, chat_id, token)

    async def record_feedback(self, chat_id: int, job_uid: str, vote: str) -> None:
        await asyncio.to_thread(self._record_feedback_sync, chat_id, job_uid, vote)

    async def get_recent_feedback(self, chat_id: int, limit: int = 12) -> List[dict]:
        """Most recent (vote, title, company) rows for a user, newest first."""
        return await asyncio.to_thread(self._get_recent_feedback_sync, chat_id, limit)

    async def get_feedback_counts(self, chat_id: int) -> tuple[int, int]:
        """(up_count, down_count) for a user."""
        return await asyncio.to_thread(self._get_feedback_counts_sync, chat_id)

    async def get_persona_stats(self) -> List[dict]:
        """[{persona, total, activated}, ...] across all users, one row per variant."""
        return await asyncio.to_thread(self._get_persona_stats_sync)
