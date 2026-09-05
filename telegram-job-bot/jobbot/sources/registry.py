from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import yaml

from .base import JobSource
from .greenhouse import GreenhouseSource
from .lever import LeverSource
from .remotive import RemotiveSource
from .rss import RSSSource

logger = logging.getLogger(__name__)


def load_sources(config_path: str) -> List[JobSource]:
    """Build the list of JobSource instances described by sources.yaml.

    A missing or empty config yields an empty list rather than raising -
    the bot still starts up (and commands still work), it just won't have
    anything to poll until the file is filled in.
    """
    path = Path(config_path)
    if not path.exists():
        logger.warning("Sources config %s not found - no job sources loaded", config_path)
        return []

    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    sources: List[JobSource] = []

    for token in config.get("greenhouse_boards") or []:
        sources.append(GreenhouseSource(token))

    for company in config.get("lever_boards") or []:
        sources.append(LeverSource(company))

    remotive_cfg = config.get("remotive") or {}
    if remotive_cfg.get("enabled"):
        sources.append(RemotiveSource(query=remotive_cfg.get("query", "")))

    for url in config.get("rss_feeds") or []:
        sources.append(RSSSource(url))

    logger.info("Loaded %d job source(s) from %s", len(sources), config_path)
    return sources
