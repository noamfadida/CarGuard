from __future__ import annotations

import logging
from typing import List

import httpx

from ..models import Job
from .base import JobSource

logger = logging.getLogger(__name__)

API_URL = "https://api.lever.co/v0/postings/{company}"


class LeverSource(JobSource):
    """Fetches open postings from a company's public Lever job board.

    Find a company's slug from its careers page URL:
    jobs.lever.co/<company> -> company.
    """

    def __init__(self, company: str, timeout: float = 20.0):
        self.company = company
        self.name = f"lever:{company}"
        self.timeout = timeout

    async def fetch(self) -> List[Job]:
        url = API_URL.format(company=self.company)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, params={"mode": "json"})
        if resp.status_code == 404:
            logger.warning("Lever board %r not found (404) - check the slug in sources.yaml", self.company)
            return []
        resp.raise_for_status()
        data = resp.json()

        jobs: List[Job] = []
        for item in data:
            categories = item.get("categories") or {}
            jobs.append(
                Job(
                    source=self.name,
                    job_id=str(item.get("id")),
                    title=item.get("text", ""),
                    company=self.company,
                    location=categories.get("location", "") or "",
                    url=item.get("hostedUrl", ""),
                    description=item.get("descriptionPlain") or item.get("description") or "",
                )
            )
        return jobs
