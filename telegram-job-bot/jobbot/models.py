from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Job:
    """A single job posting, normalized across sources."""

    source: str
    job_id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    posted_at: Optional[datetime] = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def uid(self) -> str:
        """Globally unique id, stable across polls, used for de-duplication."""
        return f"{self.source}:{self.job_id}"

    def short_description(self, max_len: int = 600) -> str:
        text = " ".join(self.description.split())
        return text[:max_len]


@dataclass
class UserProfile:
    """A Telegram user's subscription settings."""

    chat_id: int
    keywords: list[str] = field(default_factory=list)
    location: str = ""
    profile_text: str = ""
    active: bool = True
