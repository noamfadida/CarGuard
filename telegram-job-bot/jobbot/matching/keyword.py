from __future__ import annotations

from typing import Iterable

from ..models import Job

REMOTE_ALIASES = {"remote", "anywhere", "wfh"}


def keyword_match(job: Job, keywords: Iterable[str], location: str) -> bool:
    """Cheap pre-filter, always run before any LLM call.

    Empty keywords/location means "no restriction on that dimension" - a
    user with nothing configured yet matches everything.
    """
    clean_keywords = [k.strip().lower() for k in keywords if k and k.strip()]
    clean_location = (location or "").strip().lower()

    haystack = " ".join([job.title, job.description, job.location, job.company]).lower()

    if clean_keywords and not any(k in haystack for k in clean_keywords):
        return False

    if clean_location:
        if clean_location in REMOTE_ALIASES:
            if "remote" not in haystack:
                return False
        elif clean_location not in job.location.lower() and clean_location not in haystack:
            return False

    return True
