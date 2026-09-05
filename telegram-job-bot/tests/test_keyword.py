from jobbot.matching.keyword import keyword_match
from jobbot.models import Job


def make_job(**overrides) -> Job:
    defaults = dict(
        source="test",
        job_id="1",
        title="Senior Backend Engineer",
        company="Acme",
        location="Tel Aviv, Israel",
        url="https://example.com/1",
        description="Python, Django, PostgreSQL. Fintech product.",
    )
    defaults.update(overrides)
    return Job(**defaults)


def test_no_filters_matches_everything():
    job = make_job()
    assert keyword_match(job, [], "") is True


def test_keyword_match_on_title():
    job = make_job()
    assert keyword_match(job, ["backend"], "") is True


def test_keyword_match_on_description():
    job = make_job()
    assert keyword_match(job, ["django"], "") is True


def test_keyword_no_match():
    job = make_job()
    assert keyword_match(job, ["frontend", "react"], "") is False


def test_keyword_match_is_case_insensitive():
    job = make_job()
    assert keyword_match(job, ["PYTHON"], "") is True


def test_location_match_substring():
    job = make_job()
    assert keyword_match(job, [], "Tel Aviv") is True
    assert keyword_match(job, [], "Haifa") is False


def test_remote_alias_requires_remote_in_text():
    onsite = make_job()
    assert keyword_match(onsite, [], "remote") is False

    remote_job = make_job(location="Remote", description="Fully remote position")
    assert keyword_match(remote_job, [], "remote") is True


def test_keyword_and_location_both_required():
    job = make_job()
    assert keyword_match(job, ["python"], "Tel Aviv") is True
    assert keyword_match(job, ["python"], "Haifa") is False
    assert keyword_match(job, ["java"], "Tel Aviv") is False
