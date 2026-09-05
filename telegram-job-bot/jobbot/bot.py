from __future__ import annotations

import logging

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from .config import settings
from .feedback import UP, parse_callback_data
from .matching.llm import LLMMatcher
from .models import UserProfile
from .personas import assign_persona, get_persona
from .poller import fetch_all_jobs, notify_user, poll_once
from .sources.registry import load_sources
from .storage import Storage

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "I watch job boards and DM you postings that match your filters.\n\n"
    "Tap 👍/👎 on any job I send — it teaches future matching what you actually "
    "want, on top of these filters:\n\n"
    "Commands:\n"
    "/setkeywords python, backend, fintech — comma separated, matched against title/description\n"
    "/setlocation Tel Aviv (or \"remote\") — send with no text to clear\n"
    "/setprofile <free text> — describe what you're looking for in your own words; "
    "an AI re-ranks keyword matches against this (and your 👍/👎 history) before you're notified\n"
    "/status — show your current filters\n"
    "/preferences — show how many jobs you've marked 👍/👎 so far\n"
    "/pause — stop notifications\n"
    "/resume — restart notifications\n"
    "/checknow — run a check for you right now, instead of waiting for the schedule\n"
    "/help — show this again"
)


async def get_or_create_user(storage: Storage, chat_id: int) -> UserProfile:
    user = await storage.get_user(chat_id)
    if user is None:
        user = UserProfile(chat_id=chat_id)
        await storage.upsert_user(user)
    return user


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registers the user and greets them with their assigned /start persona.

    New users get a persona assigned once, at random, and it's persisted -
    this is the /start wording A/B test from the design doc. An existing
    user from before this feature shipped gets one backfilled the first
    time they hit /start again, rather than staying stuck with none.
    """
    storage: Storage = context.bot_data["storage"]
    chat_id = update.effective_chat.id
    user = await storage.get_user(chat_id)
    if user is None:
        user = UserProfile(chat_id=chat_id, persona=assign_persona().key)
        await storage.upsert_user(user)
    elif not user.persona:
        user.persona = assign_persona().key
        await storage.upsert_user(user)

    persona = get_persona(user.persona)
    await update.message.reply_text(f"{persona.start_line}\n\n{HELP_TEXT}")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


async def cmd_setkeywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.bot_data["storage"]
    user = await get_or_create_user(storage, update.effective_chat.id)
    text = " ".join(context.args)
    keywords = [k.strip() for k in text.split(",") if k.strip()]
    user.keywords = keywords
    await storage.upsert_user(user)
    if keywords:
        await update.message.reply_text(f"Keywords set to: {', '.join(keywords)}")
    else:
        await update.message.reply_text("Keywords cleared — all postings pass the keyword filter now.")


async def cmd_setlocation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.bot_data["storage"]
    user = await get_or_create_user(storage, update.effective_chat.id)
    location = " ".join(context.args).strip()
    user.location = location
    await storage.upsert_user(user)
    await update.message.reply_text(f"Location filter set to: {location or '(none)'}")


async def cmd_setprofile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.bot_data["storage"]
    user = await get_or_create_user(storage, update.effective_chat.id)
    profile_text = " ".join(context.args).strip()
    user.profile_text = profile_text
    await storage.upsert_user(user)
    if not profile_text:
        await update.message.reply_text("Profile cleared — matching falls back to keywords/location only.")
    elif settings.llm_enabled:
        await update.message.reply_text("Profile saved — new matches will be AI-ranked against it.")
    else:
        await update.message.reply_text(
            "Profile saved, but no ANTHROPIC_API_KEY is configured on this bot, so it isn't used yet "
            "(matching still falls back to keywords/location)."
        )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.bot_data["storage"]
    user = await get_or_create_user(storage, update.effective_chat.id)
    lines = [
        f"Active: {'yes' if user.active else 'no (paused)'}",
        f"Keywords: {', '.join(user.keywords) or '(none)'}",
        f"Location: {user.location or '(none)'}",
        f"Profile: {user.profile_text or '(none)'}",
        f"AI re-ranking: {'on' if settings.llm_enabled else 'off (no ANTHROPIC_API_KEY set on the bot)'}",
    ]
    await update.message.reply_text("\n".join(lines))


async def cmd_preferences(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.bot_data["storage"]
    chat_id = update.effective_chat.id
    ups, downs = await storage.get_feedback_counts(chat_id)
    footer = (
        "This shapes your future AI-ranked matches."
        if settings.llm_enabled
        else "Recorded, but AI re-ranking is off on this bot (no ANTHROPIC_API_KEY), so it isn't used to shape matches yet."
    )
    await update.message.reply_text(f"👍 Interested: {ups}\n👎 Skipped: {downs}\n\n{footer}")


async def cmd_variants(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only: activation rate per /start persona variant.

    Restricted to ADMIN_CHAT_ID so the A/B test's internals aren't exposed
    to everyone who happens to type the command.
    """
    chat_id = update.effective_chat.id
    if settings.admin_chat_id is None or chat_id != settings.admin_chat_id:
        await update.message.reply_text("This command isn't available.")
        return

    storage: Storage = context.bot_data["storage"]
    stats = await storage.get_persona_stats()
    if not stats:
        await update.message.reply_text("No users yet.")
        return

    lines = ["Persona A/B — activation by variant:"]
    for row in stats:
        name = get_persona(row["persona"]).name if row["persona"] else "(unassigned)"
        total = row["total"]
        activated = row["activated"] or 0
        pct = f" ({activated / total:.0%})" if total else ""
        lines.append(f"• {name}: {activated}/{total} activated{pct}")
    await update.message.reply_text("\n".join(lines))


async def on_feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles a 👍/👎 tap on a job message."""
    query = update.callback_query
    if query is None or query.message is None:
        return

    parsed = parse_callback_data(query.data)
    if parsed is None:
        await query.answer()
        return
    vote, token = parsed

    storage: Storage = context.bot_data["storage"]
    chat_id = query.message.chat_id
    sent_job = await storage.get_sent_job(chat_id, token)
    if sent_job is None:
        # Bot data was reset, or this button is from a very old message.
        await query.answer("This one's expired.")
        return

    await storage.record_feedback(chat_id, sent_job["job_uid"], vote)
    toast = "Noted — more like this 👍" if vote == UP else "Noted — fewer like this 👎"
    await query.answer(toast)

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except BadRequest:
        pass  # message too old to edit, or already edited — the vote is recorded either way


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.bot_data["storage"]
    user = await get_or_create_user(storage, update.effective_chat.id)
    user.active = False
    await storage.upsert_user(user)
    await update.message.reply_text("Paused. Send /resume to start getting jobs again.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.bot_data["storage"]
    user = await get_or_create_user(storage, update.effective_chat.id)
    user.active = True
    await storage.upsert_user(user)
    await update.message.reply_text("Resumed — you'll get new matches on the next check.")


async def cmd_checknow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.bot_data["storage"]
    user = await get_or_create_user(storage, update.effective_chat.id)
    if not user.active:
        await update.message.reply_text("You're paused — send /resume first.")
        return

    await update.message.reply_text("Checking now…")
    sources = context.bot_data["sources"]
    llm = context.bot_data.get("llm")
    jobs = await fetch_all_jobs(sources)
    sent = await notify_user(context.bot, storage, user, jobs, llm, settings.max_jobs_per_run)
    if not sent:
        await update.message.reply_text("No new matches right now.")


async def job_queue_poll(context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.bot_data["storage"]
    sources = context.bot_data["sources"]
    llm = context.bot_data.get("llm")
    await poll_once(context.bot, storage, sources, llm, settings.max_jobs_per_run)


def build_application() -> Application:
    if not settings.telegram_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set — copy .env.example to .env and fill it in")

    application = Application.builder().token(settings.telegram_token).build()

    storage = Storage(settings.db_path)
    sources = load_sources(settings.sources_config_path)
    llm = LLMMatcher(settings.anthropic_api_key, settings.anthropic_model) if settings.llm_enabled else None

    application.bot_data["storage"] = storage
    application.bot_data["sources"] = sources
    application.bot_data["llm"] = llm

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("setkeywords", cmd_setkeywords))
    application.add_handler(CommandHandler("setlocation", cmd_setlocation))
    application.add_handler(CommandHandler("setprofile", cmd_setprofile))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("preferences", cmd_preferences))
    application.add_handler(CommandHandler("pause", cmd_pause))
    application.add_handler(CommandHandler("resume", cmd_resume))
    application.add_handler(CommandHandler("checknow", cmd_checknow))
    application.add_handler(CommandHandler("variants", cmd_variants))
    application.add_handler(CallbackQueryHandler(on_feedback_callback, pattern=r"^fb:"))

    if application.job_queue is not None:
        application.job_queue.run_repeating(job_queue_poll, interval=settings.poll_interval_seconds, first=10)
    else:
        logger.warning(
            "JobQueue is unavailable — install the 'job-queue' extra "
            "(python-telegram-bot[job-queue]) to enable scheduled polling"
        )

    return application


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    application = build_application()
    logger.info(
        "Starting CareerPing bot (poll interval: %ss, %d source(s), AI re-ranking %s)",
        settings.poll_interval_seconds,
        len(application.bot_data["sources"]),
        "on" if settings.llm_enabled else "off",
    )
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
