from jobbot.models import Job


def test_job_uid_combines_source_and_id():
    job = Job(source="greenhouse:wix", job_id="42", title="t", company="c", location="l", url="u")
    assert job.uid == "greenhouse:wix:42"


def test_short_description_collapses_whitespace_and_truncates():
    job = Job(
        source="s",
        job_id="1",
        title="t",
        company="c",
        location="l",
        url="u",
        description="line one\n\n   line   two  ",
    )
    assert job.short_description() == "line one line two"
    assert job.short_description(max_len=4) == "line"
