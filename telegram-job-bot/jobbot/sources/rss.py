from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import List, Optional

import feedparser

from ..models import Job
from .base import JobSource

logger = logging.getLogger(__name__)


class RSSSource(JobSource):
    """Generic RSS/Atom feed source.

    Works with any job-board feed that emits RSS - a saved-search feed from
    a job board, a company careers-page feed, an aggregator, etc. This is
    the escape hatch for sources that don't have a clean JSON API.
    """

    def __init__(self, url: str, label: Optional[str] = None):
        self.url = url
        self.name = f"rss:{label or url}"

    async def fetch(self) -> List[Job]:
        feed = await asyncio.to_thread(feedparser.parse, self.url)
        if getattr(feed, "bozo", False) and not feed.entries:
            logger.warning("RSS feed %s failed to parse: %s", self.url, getattr(feed, "bozo_exception", ""))
            return []

        jobs: List[Job] = []
        for entry in feed.entries:
            link = entry.get("link", "")
            title = entry.get("title", "")
            entry_id = entry.get("id") or link or hashlib.sha1(f"{title}{link}".encode("utf-8")).hexdigest()
            jobs.append(
                Job(
                    source=self.name,
                    job_id=str(entry_id),
                    title=title,
                    company=entry.get("author", "") or "",
                    location="",
                    url=link,
                    description=entry.get("summary", "") or "",
                )
            )
        return jobs
