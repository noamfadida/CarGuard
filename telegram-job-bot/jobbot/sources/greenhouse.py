from __future__ import annotations

import logging
from typing import List

import httpx

from ..models import Job
from .base import JobSource

logger = logging.getLogger(__name__)

API_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


class GreenhouseSource(JobSource):
    """Fetches open postings from a company's public Greenhouse job board.

    Many tech companies (including a number of Israeli ones) use Greenhouse
    and expose this API with no auth required. Find a company's token from
    its careers page URL: boards.greenhouse.io/<token> -> token.
    """

    def __init__(self, token: str, timeout: float = 20.0):
        self.token = token
        self.name = f"greenhouse:{token}"
        self.timeout = timeout

    async def fetch(self) -> List[Job]:
        url = API_URL.format(token=self.token)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, params={"content": "true"})
        if resp.status_code == 404:
            logger.warning("Greenhouse board %r not found (404) - check the token in sources.yaml", self.token)
            return []
        resp.raise_for_status()
        data = resp.json()

        jobs: List[Job] = []
        for item in data.get("jobs", []):
            location = (item.get("location") or {}).get("name", "")
            jobs.append(
                Job(
                    source=self.name,
                    job_id=str(item["id"]),
                    title=item.get("title", ""),
                    company=self.token,
                    location=location,
                    url=item.get("absolute_url", ""),
                    description=item.get("content", "") or "",
                )
            )
        return jobs
