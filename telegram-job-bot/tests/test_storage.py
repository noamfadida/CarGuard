import asyncio

from jobbot.models import UserProfile
from jobbot.storage import Storage


def run(coro):
    return asyncio.run(coro)


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
    assert run(storage.has_sent(1, "greenhouse:wix:1")) is False

    run(storage.mark_sent(1, "greenhouse:wix:1"))
    assert run(storage.has_sent(1, "greenhouse:wix:1")) is True
    # A different user hasn't seen it.
    assert run(storage.has_sent(2, "greenhouse:wix:1")) is False
