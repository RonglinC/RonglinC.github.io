from __future__ import annotations

from pathlib import Path

import pytest

from resume_agent.models.resume import Resume
from resume_agent.parsers.resume_parser import parse_resume, resume_to_yaml
from resume_agent.search.job_search import (
    detect_ats,
    extract_greenhouse_board,
    extract_lever_slug,
    stable_job_key,
    _match_keywords,
)


SAMPLE_YAML = Path(__file__).parent.parent / "resume.example.yaml"


def test_parse_resume_example():
    resume = parse_resume(SAMPLE_YAML)
    assert resume.name == "Ronglin Chen"
    assert "Python" in resume.skills
    assert len(resume.experience) >= 1


def test_resume_roundtrip():
    resume = parse_resume(SAMPLE_YAML)
    yaml_text = resume_to_yaml(resume)
    reparsed = Resume.model_validate(__import__("yaml").safe_load(yaml_text))
    assert reparsed.email == resume.email


def test_match_keywords():
    assert _match_keywords("Senior Python Developer", ["python", "react"]) == 0.5
    assert _match_keywords("Designer role", ["python"]) == 0.0


def test_detect_ats():
    assert detect_ats("https://boards.greenhouse.io/stripe/jobs/123") == "greenhouse"
    assert detect_ats("https://jobs.lever.co/notion/abc-123") == "lever"
    assert detect_ats("https://example.com/jobs") is None


def test_extract_greenhouse_board():
    result = extract_greenhouse_board("https://boards.greenhouse.io/acme/jobs/12345")
    assert result == ("acme", "12345")


def test_extract_lever_slug():
    result = extract_lever_slug("https://jobs.lever.co/acme/abc-def-123")
    assert result == ("acme", "abc-def-123")


def test_stable_job_key():
    key1 = stable_job_key("Engineer", "Acme", "https://a.com")
    key2 = stable_job_key("Engineer", "Acme", "https://a.com")
    key3 = stable_job_key("Engineer", "Other", "https://a.com")
    assert key1 == key2
    assert key1 != key3


@pytest.mark.asyncio
async def test_job_search():
    from resume_agent.search.job_search import JobSearchEngine

    engine = JobSearchEngine(keywords=["developer"], min_score=0.0)
    jobs = await engine.search_all(limit=5)
    assert len(jobs) > 0
    assert jobs[0].title
    assert jobs[0].company
