from __future__ import annotations

import hashlib

UP = "up"
DOWN = "down"

CALLBACK_PREFIX = "fb"


def make_token(chat_id: int, job_uid: str) -> str:
    """A short, deterministic id for a (chat, job) pair.

    Telegram caps callback_data at 64 bytes, and a job_uid can be an
    arbitrarily long RSS entry URL, so the raw uid never goes on the wire —
    only this token does. It's looked back up against the sent_jobs table
    when the button is pressed.
    """
    digest = hashlib.sha1(f"{chat_id}:{job_uid}".encode("utf-8")).hexdigest()
    return digest[:16]


def callback_data(vote: str, token: str) -> str:
    return f"{CALLBACK_PREFIX}:{vote}:{token}"


def parse_callback_data(data: str) -> tuple[str, str] | None:
    """Returns (vote, token), or None if `data` isn't one of ours / is malformed."""
    parts = (data or "").split(":", 2)
    if len(parts) != 3 or parts[0] != CALLBACK_PREFIX or parts[1] not in (UP, DOWN):
        return None
    return parts[1], parts[2]
