from jobbot.feedback import DOWN, UP, callback_data, make_token, parse_callback_data


def test_make_token_is_deterministic_and_short():
    token = make_token(123, "greenhouse:wix:1")
    assert token == make_token(123, "greenhouse:wix:1")
    assert len(token) == 16


def test_make_token_differs_by_chat_or_job():
    base = make_token(1, "job-a")
    assert make_token(2, "job-a") != base
    assert make_token(1, "job-b") != base


def test_callback_data_roundtrips_and_stays_under_telegram_limit():
    # A long RSS job_uid (a full URL) must never leak into callback_data —
    # only the token does, so this stays tiny regardless of job_uid length.
    long_uid = "rss:" + "https://example.com/careers?" + "q=" * 200
    token = make_token(42, long_uid)
    data = callback_data(UP, token)

    assert len(data.encode("utf-8")) <= 64
    assert parse_callback_data(data) == (UP, token)


def test_parse_callback_data_rejects_unrelated_or_malformed_data():
    assert parse_callback_data("something:else") is None
    assert parse_callback_data("fb:sideways:token") is None
    assert parse_callback_data("") is None
    assert parse_callback_data(None) is None


def test_down_vote_roundtrips_too():
    token = make_token(1, "job-x")
    assert parse_callback_data(callback_data(DOWN, token)) == (DOWN, token)
