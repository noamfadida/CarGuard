# CareerPing

A Telegram bot that DMs you new job postings matching filters you set,
optionally re-ranked by an LLM against a free-text description of what
you're looking for. Built with an Israel-focused starting source list, but
sources are just config — extend it for any market.

## How it works

```
 job sources (Greenhouse / Lever / Remotive / RSS)
              │
              ▼
      fetch + normalize
              │
              ▼
   per-user keyword/location filter  ──▶ no match ──▶ dropped
              │ pass
              ▼
   already sent to this user? ─────────▶ yes ────────▶ dropped
              │ no
              ▼
   /setprofile set + ANTHROPIC_API_KEY configured?
       │ yes                              │ no
       ▼                                  ▼
  LLM relevance re-rank             send as-is
       │
       ▼
  send matches via Telegram, record as sent
```

The bot is a single long-running process: it polls Telegram for commands
(`/start`, `/setkeywords`, ...) and, on a timer, polls the configured job
sources and DMs each active user their new matches.

## Why these job sources

The big Israeli consumer job boards (AllJobs, Drushim, LinkedIn) don't
publish a free/official API, and scraping them is fragile and against
their terms of use — this project deliberately doesn't do that. Instead:

- **Greenhouse** and **Lever** are applicant-tracking systems used
  directly by a large share of Israeli tech companies, and both expose a
  free, unauthenticated, stable JSON API for their public job boards. This
  is the reliable backbone.
- **Remotive** is a free public API for remote jobs globally — not
  Israel-specific, but many listings are open to Israel-based candidates,
  and per-user filters narrow it down.
- **RSS** is a generic escape hatch: point it at any job board's feed
  (a saved-search feed, a company careers feed, an aggregator) and it's
  picked up the same way.

`sources.yaml` is where you configure all of this — see the comments in
that file for how to find a company's Greenhouse/Lever token, and note
that the shipped list is a starting point to verify/expand, not a
guarantee that every entry is still valid (a stale token just makes that
one board log a warning and get skipped, it won't break the others).

## Setup

```bash
cd telegram-job-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
- `TELEGRAM_BOT_TOKEN` — required. Create a bot with
  [@BotFather](https://t.me/BotFather) on Telegram (`/newbot`) and paste
  the token it gives you.
- `ANTHROPIC_API_KEY` — optional. Without it, the bot still runs and
  filters on keywords/location; `/setprofile` text is stored but not used
  for re-ranking until a key is set.

Edit `sources.yaml` to add the companies/feeds you care about.

Run it:

```bash
python main.py
```

## Bot commands

| Command | What it does |
| --- | --- |
| `/start` | Registers you and shows help |
| `/setkeywords python, backend, fintech` | Comma-separated keywords matched against title/description |
| `/setlocation Tel Aviv` | Location filter; use `remote` for remote-only, or send with no text to clear |
| `/setprofile <free text>` | Describe what you want in your own words; the LLM re-ranks keyword matches against this |
| `/status` | Shows your current filters and whether AI re-ranking is on |
| `/pause` / `/resume` | Stop/restart notifications without losing your filters |
| `/checknow` | Runs a check for you immediately, instead of waiting for the schedule |
| `/help` | Shows the command list |

A user with no keywords/location set matches everything from every
source, which is a lot of noise — `/setkeywords` and/or `/setlocation`
right after `/start` is the expected first move.

## Configuration reference (`.env`)

| Variable | Default | Meaning |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | — | Required |
| `ANTHROPIC_API_KEY` | — | Optional, enables `/setprofile` re-ranking |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | Model used for re-ranking |
| `POLL_INTERVAL_SECONDS` | `900` | How often all sources are checked |
| `MAX_JOBS_PER_USER_PER_RUN` | `10` | Caps how many messages one poll cycle sends one user |
| `JOBBOT_DB_PATH` | `./data/jobbot.sqlite3` | SQLite file storing users + sent-job history |
| `JOBBOT_SOURCES_PATH` | `./sources.yaml` | Path to the sources config |

## Running it long-term

This is meant to run continuously (it polls Telegram, not the other way
around). Options:

**Docker Compose** (simplest):
```bash
docker compose up -d --build
```

**systemd**, if you'd rather run it directly on a server:
```ini
# /etc/systemd/system/careerping.service
[Unit]
Description=CareerPing Telegram job bot
After=network-online.target

[Service]
WorkingDirectory=/opt/careerping
EnvironmentFile=/opt/careerping/.env
ExecStart=/opt/careerping/.venv/bin/python main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Project layout

```
telegram-job-bot/
├── main.py                  # entrypoint: python main.py
├── sources.yaml             # which job boards/feeds to poll
├── .env.example
├── jobbot/
│   ├── bot.py                # Telegram command handlers + polling job
│   ├── poller.py              # fetch → filter → notify pipeline
│   ├── storage.py             # SQLite: users, sent-job de-dup
│   ├── models.py               # Job, UserProfile
│   ├── config.py                # env var loading
│   ├── sources/                 # one module per source type
│   │   ├── greenhouse.py
│   │   ├── lever.py
│   │   ├── remotive.py
│   │   ├── rss.py
│   │   └── registry.py          # builds sources from sources.yaml
│   └── matching/
│       ├── keyword.py            # cheap pre-filter
│       └── llm.py                # optional Claude re-ranking
└── tests/
```

## Extending it

- **New source type**: add a class implementing `JobSource.fetch()` in
  `jobbot/sources/`, wire it up in `registry.py`. It just needs to return
  a list of `Job`s — the rest of the pipeline (dedup, filtering, sending)
  is source-agnostic.
- **New job market**: nothing in the pipeline is Israel-specific — it's
  purely `sources.yaml` content plus each user's own filters.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests cover the keyword filter, the `Job`/`UserProfile` models, and
storage (SQLite round-trips, dedup). They don't hit the network — the
`JobSource` implementations and the LLM re-ranker aren't covered by
automated tests since they wrap third-party APIs; exercise those with
`/checknow` against a real bot token once configured.
