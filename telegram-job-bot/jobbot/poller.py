from __future__ import annotations

import logging
from html import escape
from typing import List, Optional, Tuple

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden

from .feedback import DOWN, UP, callback_data, make_token
from .matching.keyword import keyword_match
from .matching.llm import LLMMatcher
from .models import Job, UserProfile
from .sources.base import JobSource
from .storage import Storage

logger = logging.getLogger(__name__)


async def fetch_all_jobs(sources: List[JobSource]) -> List[Job]:
    all_jobs: List[Job] = []
    for source in sources:
        try:
            jobs = await source.fetch()
            logger.info("Fetched %d job(s) from %s", len(jobs), source.name)
            all_jobs.extend(jobs)
        except Exception:
            logger.exception("Job source %s failed - skipping it this round", source.name)
    return all_jobs


def format_job_message(job: Job, reason: Optional[str] = None) -> str:
    lines = [
        f"<b>{escape(job.title or '(untitled)')}</b>",
        f"{escape(job.company or 'unknown company')} — {escape(job.location or 'n/a')}",
    ]
    if reason:
        lines.append(f"<i>{escape(reason)}</i>")
    if job.url:
        lines.append(escape(job.url))
    return "\n".join(lines)


def build_feedback_keyboard(chat_id: int, job_uid: str) -> InlineKeyboardMarkup:
    token = make_token(chat_id, job_uid)
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👍 Interested", callback_data=callback_data(UP, token)),
                InlineKeyboardButton("👎 Skip", callback_data=callback_data(DOWN, token)),
            ]
        ]
    )


async def build_feedback_context(storage: Storage, chat_id: int, limit: int = 12) -> str:
    """A short summary of a user's past 👍/👎 votes, for the LLM prompt.

    Empty string (not None) when there's no feedback yet, so callers can
    always safely include it.
    """
    recent = await storage.get_recent_feedback(chat_id, limit=limit)
    if not recent:
        return ""

    liked = [f"{r['title']} at {r['company']}" for r in recent if r["vote"] == UP]
    disliked = [f"{r['title']} at {r['company']}" for r in recent if r["vote"] == DOWN]

    lines = []
    if liked:
        lines.append("Marked INTERESTED in: " + "; ".join(liked))
    if disliked:
        lines.append("Marked NOT INTERESTED in: " + "; ".join(disliked))
    return "\n".join(lines)


async def notify_user(
    bot: Bot,
    storage: Storage,
    user: UserProfile,
    jobs: List[Job],
    llm: Optional[LLMMatcher],
    max_per_run: int,
) -> int:
    """Filter `jobs` for one user and send the new matches. Returns count sent."""
    candidates = [j for j in jobs if keyword_match(j, user.keywords, user.location)]

    unseen: List[Job] = []
    for job in candidates:
        if not await storage.has_sent(user.chat_id, job.uid):
            unseen.append(job)

    to_send: List[Tuple[Job, Optional[str]]]
    if user.profile_text and llm is not None and unseen:
        feedback_context = await build_feedback_context(storage, user.chat_id)
        to_send = list(await llm.filter_relevant(unseen, user.profile_text, feedback_context))
    else:
        to_send = [(job, None) for job in unseen]

    sent = 0
    for job, reason in to_send[:max_per_run]:
        try:
            await bot.send_message(
                chat_id=user.chat_id,
                text=format_job_message(job, reason),
                parse_mode=ParseMode.HTML,
                reply_markup=build_feedback_keyboard(user.chat_id, job.uid),
                disable_web_page_preview=False,
            )
        except Forbidden:
            logger.warning("User %s blocked the bot - deactivating their subscription", user.chat_id)
            user.active = False
            await storage.upsert_user(user)
            break
        except BadRequest:
            logger.exception("Failed to send job %s to chat %s", job.uid, user.chat_id)
            continue
        else:
            sent += 1
            await storage.mark_sent(user.chat_id, job, make_token(user.chat_id, job.uid))
    return sent


async def poll_once(
    bot: Bot,
    storage: Storage,
    sources: List[JobSource],
    llm: Optional[LLMMatcher],
    max_per_run: int,
) -> None:
    jobs = await fetch_all_jobs(sources)
    if not jobs:
        logger.info("No jobs fetched this round (no sources configured, or all sources failed/empty)")
        return

    users = await storage.get_active_users()
    logger.info("Checking %d job(s) against %d active user(s)", len(jobs), len(users))
    for user in users:
        try:
            sent = await notify_user(bot, storage, user, jobs, llm, max_per_run)
            if sent:
                logger.info("Sent %d new job(s) to chat %s", sent, user.chat_id)
        except Exception:
            logger.exception("Failed to process user %s this round", user.chat_id)
