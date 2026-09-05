from __future__ import annotations

import logging
from typing import List

import httpx

from ..models import Job
from .base import JobSource

logger = logging.getLogger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"


class RemotiveSource(JobSource):
    """Fetches postings from Remotive's free public remote-jobs API.

    Global remote listings, not Israel-specific - useful as a broad source
    that per-user keyword/location filters (e.g. "Israel", "Tel Aviv",
    "remote") narrow down downstream.
    """

    def __init__(self, query: str = "", timeout: float = 20.0):
        self.query = query
        self.name = f"remotive:{query or 'all'}"
        self.timeout = timeout

    async def fetch(self) -> List[Job]:
        params = {"search": self.query} if self.query else {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        jobs: List[Job] = []
        for item in data.get("jobs", []):
            jobs.append(
                Job(
                    source=self.name,
                    job_id=str(item.get("id")),
                    title=item.get("title", ""),
                    company=item.get("company_name", "") or "",
                    location=item.get("candidate_required_location", "") or "",
                    url=item.get("url", ""),
                    description=item.get("description", "") or "",
                )
            )
        return jobs
