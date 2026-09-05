from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from ..models import Job


class JobSource(ABC):
    """A pluggable source of job postings.

    Implementations should raise on genuine failures (network error,
    unexpected schema); the poller catches and logs per-source failures
    so one broken source never blocks the others.
    """

    name: str

    @abstractmethod
    async def fetch(self) -> List[Job]:
        raise NotImplementedError
