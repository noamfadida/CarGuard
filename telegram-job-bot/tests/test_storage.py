import asyncio

from jobbot.feedback import DOWN, UP, make_token
from jobbot.models import Job, UserProfile
from jobbot.storage import Storage


def run(coro):
    return asyncio.run(coro)


def make_job(**overrides) -> Job:
    defaults = dict(
        source="greenhouse:wix",
        job_id="1",
        title="Senior Backend Engineer",
        company="Wix",
        location="Tel Aviv, Israel",
        url="https://example.com/1",
    )
    defaults.update(overrides)
    return Job(**defaults)


def test_unknown_user_returns_none(tmp_path):
    storage = Storage(str(tmp_path / "test.sqlite3"))
    assert run(storage.get_user(123)) is None


def test_upsert_and_get_user_roundtrip(tmp_path):
    storage = Storage(str(tmp_path / "test.sqlite3"))
    user = UserProfile(chat_id=1, keywords=["python", "backend"], location="Tel Aviv", profile_text="hi")
    run(storage.upsert_user(user))

    fetched = run(storage.get_user(1))
    assert fetched is not None
    assert fetched.keywords == ["python", "backend"]
    assert fetched.location == "Tel Aviv"
    assert fetched.profile_text == "hi"
    assert fetched.active is True


def test_get_active_users_excludes_paused(tmp_path):
    storage = Storage(str(tmp_path / "test.sqlite3"))
    run(storage.upsert_user(UserProfile(chat_id=1, active=True)))
    run(storage.upsert_user(UserProfile(chat_id=2, active=False)))

    active = run(storage.get_active_users())
    assert [u.chat_id for u in active] == [1]


def test_mark_sent_and_has_sent(tmp_path):
    storage = Storage(str(tmp_path / "test.sqlite3"))
    job = make_job()
    assert run(storage.has_sent(1, job.uid)) is False

    run(storage.mark_sent(1, job, make_token(1, job.uid)))
    assert run(storage.has_sent(1, job.uid)) is True
    # A different user hasn't seen it.
    assert run(storage.has_sent(2, job.uid)) is False


def test_get_sent_job_resolves_token(tmp_path):
    storage = Storage(str(tmp_path / "test.sqlite3"))
    job = make_job()
    token = make_token(1, job.uid)
    run(storage.mark_sent(1, job, token))

    resolved = run(storage.get_sent_job(1, token))
    assert resolved == {
        "job_uid": job.uid,
        "title": job.title,
        "company": job.company,
        "location": job.location,
    }

    # Unknown token, or the right token under the wrong chat, both miss.
    assert run(storage.get_sent_job(1, "not-a-real-token")) is None
    assert run(storage.get_sent_job(2, token)) is None


def test_record_feedback_and_counts(tmp_path):
    storage = Storage(str(tmp_path / "test.sqlite3"))
    job_a, job_b = make_job(job_id="1"), make_job(job_id="2", title="Frontend Engineer")
    run(storage.mark_sent(1, job_a, make_token(1, job_a.uid)))
    run(storage.mark_sent(1, job_b, make_token(1, job_b.uid)))

    run(storage.record_feedback(1, job_a.uid, UP))
    run(storage.record_feedback(1, job_b.uid, DOWN))

    assert run(storage.get_feedback_counts(1)) == (1, 1)
    # No feedback recorded for a fresh user.
    assert run(storage.get_feedback_counts(2)) == (0, 0)


def test_record_feedback_overwrites_previous_vote(tmp_path):
    storage = Storage(str(tmp_path / "test.sqlite3"))
    job = make_job()
    run(storage.mark_sent(1, job, make_token(1, job.uid)))

    run(storage.record_feedback(1, job.uid, DOWN))
    run(storage.record_feedback(1, job.uid, UP))

    assert run(storage.get_feedback_counts(1)) == (1, 0)


def test_get_recent_feedback_includes_title_and_company(tmp_path):
    storage = Storage(str(tmp_path / "test.sqlite3"))
    job = make_job()
    run(storage.mark_sent(1, job, make_token(1, job.uid)))
    run(storage.record_feedback(1, job.uid, UP))

    recent = run(storage.get_recent_feedback(1))
    assert recent == [{"vote": UP, "title": job.title, "company": job.company}]


def test_persona_persists_across_roundtrip(tmp_path):
    storage = Storage(str(tmp_path / "test.sqlite3"))
    run(storage.upsert_user(UserProfile(chat_id=1, persona="tomer")))

    fetched = run(storage.get_user(1))
    assert fetched.persona == "tomer"


def test_persona_stats_groups_by_variant_and_counts_activation(tmp_path):
    storage = Storage(str(tmp_path / "test.sqlite3"))
    # roni: one activated (has keywords), one not
    run(storage.upsert_user(UserProfile(chat_id=1, persona="roni", keywords=["python"])))
    run(storage.upsert_user(UserProfile(chat_id=2, persona="roni")))
    # tomer: one activated (has a profile)
    run(storage.upsert_user(UserProfile(chat_id=3, persona="tomer", profile_text="backend eng")))

    stats = {row["persona"]: row for row in run(storage.get_persona_stats())}
    assert stats["roni"]["total"] == 2
    assert stats["roni"]["activated"] == 1
    assert stats["tomer"]["total"] == 1
    assert stats["tomer"]["activated"] == 1
