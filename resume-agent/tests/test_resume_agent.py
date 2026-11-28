from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter

from resume_agent.config import resolve_config, AgentConfig
from resume_agent.models.resume import Resume
from resume_agent.parsers.pdf_parser import extract_text_from_pdf, parse_pdf_resume
from resume_agent.parsers.resume_parser import parse_resume, resume_to_yaml
from resume_agent.search.job_search import (
    detect_ats,
    extract_greenhouse_board,
    extract_lever_slug,
    stable_job_key,
    _match_keywords,
)


SAMPLE_YAML = Path(__file__).parent.parent / "resume.example.yaml"
FIXTURES = Path(__file__).parent / "fixtures"


def _make_sample_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    page = writer.pages[0]
    # pypdf blank pages have no text layer; use a minimal PDF with text via reportlab alternative
    writer.write(path)


def _make_text_pdf(path: Path, text: str) -> None:
    """Create a minimal PDF with embedded text using pypdf merge from a simple approach."""
    from pypdf import PdfReader

    # Build PDF manually with a text stream (minimal valid PDF)
    lines = text.replace("(", r"\(").replace(")", r"\)").split("\n")
    y = 750
    content_lines = ["BT", "/F1 12 Tf"]
    for line in lines:
        content_lines.append(f"50 {y} Td ({line}) Tj")
        content_lines.append("0 -16 Td")
        y -= 16
    content_lines.append("ET")
    stream = "\n".join(content_lines)

    pdf_bytes = f"""%PDF-1.4
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj
4 0 obj<< /Length {len(stream)} >>stream
{stream}
endstream endobj
5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000{300 + len(stream):03d} 00000 n 
trailer<< /Size 6 /Root 1 0 R >>
startxref
{400 + len(stream)}
%%EOF"""
    path.write_bytes(pdf_bytes.encode("latin-1"))


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "resume.pdf"
    _make_text_pdf(
        pdf_path,
        """Ronglin Chen
ronglin@example.com
+1-555-123-4567
https://linkedin.com/in/ronglin
https://github.com/RonglinC

Summary
Full-stack developer with Python, JavaScript, React experience.

Skills
Python, JavaScript, React, Node.js, AWS

Experience
Senior Engineer Example Corp 2022 - Present
""",
    )
    return pdf_path


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


def test_parse_pdf_resume(sample_pdf: Path, tmp_path: Path):
    resume = parse_pdf_resume(sample_pdf, cache_dir=tmp_path / "cache", use_openai=False)
    assert resume.name == "Ronglin Chen"
    assert resume.email == "ronglin@example.com"
    assert "Python" in resume.skills
    assert resume.linkedin is not None


def test_pdf_cache(sample_pdf: Path, tmp_path: Path):
    cache_dir = tmp_path / "cache"
    first = parse_pdf_resume(sample_pdf, cache_dir=cache_dir, use_openai=False)
    second = parse_pdf_resume(sample_pdf, cache_dir=cache_dir, use_openai=False)
    assert first.email == second.email
    assert len(list(cache_dir.glob("*.yaml"))) == 1


def test_resolve_config_sets_pdf_path():
    config = resolve_config(AgentConfig(resume_path=Path("my-resume.pdf")))
    assert config.resume_pdf_path == Path("my-resume.pdf")


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
