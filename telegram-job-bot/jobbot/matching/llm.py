from __future__ import annotations

import json
import logging
from typing import List, Tuple

from anthropic import AsyncAnthropic

from ..models import Job

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You screen job postings for one candidate. You are given the candidate's "
    "own description of what they are looking for, and a batch of candidate "
    "job postings that already passed a keyword pre-filter. For each posting, "
    "decide whether it is genuinely a good match for that candidate given "
    "their stated role, seniority, skills, and location preferences. Be "
    "reasonably strict: prefer a false negative over spamming the candidate "
    "with loosely-related roles.\n\n"
    "Respond with ONLY a JSON array, no prose before or after it, exactly one "
    "object per input job in the same order, shaped as:\n"
    '[{"id": "<job id>", "relevant": true|false, "reason": "<one short sentence>"}]'
)


class LLMMatcher:
    """Optional relevance re-ranking step on top of the keyword filter.

    Only invoked for users who've set a free-text /setprofile description -
    everyone else stays on keyword/location matching alone.
    """

    def __init__(self, api_key: str, model: str):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def filter_relevant(
        self, jobs: List[Job], profile_text: str, batch_size: int = 15
    ) -> List[Tuple[Job, str]]:
        results: List[Tuple[Job, str]] = []
        for i in range(0, len(jobs), batch_size):
            batch = jobs[i : i + batch_size]
            try:
                verdicts = await self._score_batch(batch, profile_text)
            except Exception:
                logger.exception("LLM relevance scoring failed for a batch of %d jobs; skipping it", len(batch))
                continue

            by_uid = {str(v.get("id")): v for v in verdicts}
            for job in batch:
                verdict = by_uid.get(job.uid)
                if verdict and verdict.get("relevant"):
                    results.append((job, str(verdict.get("reason", ""))))
        return results

    async def _score_batch(self, jobs: List[Job], profile_text: str) -> list:
        listing = [
            {
                "id": job.uid,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "description": job.short_description(1200),
            }
            for job in jobs
        ]
        user_content = (
            f"Candidate profile:\n{profile_text}\n\n"
            f"Job postings (JSON):\n{json.dumps(listing, ensure_ascii=False)}"
        )
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        return json.loads(text)
