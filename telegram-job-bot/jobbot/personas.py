from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Persona:
    key: str
    name: str
    start_line: str


# The /start persona A/B test (see the design doc, "Naming" section). Each
# new user is randomly assigned one of these; the line is what they see as
# the bot's very first message. Add/remove variants here to change what's
# being tested - nothing else needs touching.
PERSONAS: List[Persona] = [
    Persona(
        key="roni",
        name="Roni",
        start_line="Hi, I'm Roni. I'll DM you new job postings that match your filters.",
    ),
    Persona(
        key="tomer",
        name="Tomer",
        start_line="Tomer here — I'll ping you the moment a job worth applying to shows up.",
    ),
    Persona(
        key="gali",
        name="Gali",
        start_line="Hey, I'm Gali. Jobs land here before the crowd applies.",
    ),
]

_BY_KEY = {p.key: p for p in PERSONAS}


def assign_persona() -> Persona:
    """Called once per new user, at /start."""
    return random.choice(PERSONAS)


def get_persona(key: str) -> Persona:
    """Looks up a stored persona key; unknown or empty keys fall back to the first variant."""
    return _BY_KEY.get(key, PERSONAS[0])
