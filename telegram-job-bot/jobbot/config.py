from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    anthropic_api_key: str
    anthropic_model: str
    poll_interval_seconds: int
    max_jobs_per_run: int
    db_path: str
    sources_config_path: str
    http_timeout_seconds: float

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


def load_settings() -> Settings:
    return Settings(
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "900")),
        max_jobs_per_run=int(os.getenv("MAX_JOBS_PER_USER_PER_RUN", "10")),
        db_path=os.getenv("JOBBOT_DB_PATH", str(BASE_DIR / "data" / "jobbot.sqlite3")),
        sources_config_path=os.getenv("JOBBOT_SOURCES_PATH", str(BASE_DIR / "sources.yaml")),
        http_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "20")),
    )


settings = load_settings()
