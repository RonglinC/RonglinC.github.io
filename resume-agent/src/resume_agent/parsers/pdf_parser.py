from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml
from pypdf import PdfReader

from resume_agent.models.resume import Education, Resume, WorkExperience

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}"
)
LINKEDIN_RE = re.compile(r"(https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?)", re.I)
GITHUB_RE = re.compile(r"(https?://(?:www\.)?github\.com/[a-zA-Z0-9_-]+/?)", re.I)
URL_RE = re.compile(r"https?://[^\s,)]+", re.I)

COMMON_SKILLS = [
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust", "Ruby", "PHP",
    "React", "Vue", "Angular", "Node.js", "Django", "Flask", "FastAPI", "Spring",
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Docker", "Kubernetes",
    "AWS", "GCP", "Azure", "Git", "Linux", "HTML", "CSS", "GraphQL", "REST",
    "Machine Learning", "TensorFlow", "PyTorch", "Spark", "Kafka",
]

SECTION_HEADERS = {
    "experience": re.compile(r"^(work\s*)?experience|employment|professional\s*experience", re.I),
    "education": re.compile(r"^education|academic", re.I),
    "skills": re.compile(r"^skills|technical\s*skills|technologies", re.I),
    "summary": re.compile(r"^summary|profile|about(\s*me)?|objective", re.I),
}


def extract_text_from_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _cache_key(path: Path) -> str:
    stat = path.stat()
    raw = f"{path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _load_cache(cache_dir: Path, key: str) -> Resume | None:
    cache_file = cache_dir / f"{key}.yaml"
    if cache_file.exists():
        with cache_file.open(encoding="utf-8") as f:
            return Resume.model_validate(yaml.safe_load(f))
    return None


def _save_cache(cache_dir: Path, key: str, resume: Resume) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{key}.yaml"
    cache_file.write_text(
        yaml.dump(
            resume.model_dump(mode="json", exclude_none=True),
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _extract_name(lines: list[str], email: str | None) -> str:
    for line in lines[:8]:
        cleaned = line.strip()
        if not cleaned or len(cleaned) > 60:
            continue
        if EMAIL_RE.search(cleaned) or URL_RE.search(cleaned) or PHONE_RE.fullmatch(cleaned):
            continue
        if SECTION_HEADERS["summary"].match(cleaned):
            continue
        if re.match(r"^[A-Z][a-zA-Z\u4e00-\u9fff]+(?:[\s\-][A-Z][a-zA-Z\u4e00-\u9fff]+)+$", cleaned):
            return cleaned
        if len(cleaned.split()) <= 4 and not any(ch.isdigit() for ch in cleaned):
            return cleaned
    if email:
        local = email.split("@")[0]
        return local.replace(".", " ").replace("_", " ").title()
    return "Candidate"


def _extract_skills(text: str) -> list[str]:
    text_lower = text.lower()
    found = [skill for skill in COMMON_SKILLS if skill.lower() in text_lower]
    skills_match = SECTION_HEADERS["skills"].search(text)
    if skills_match:
        section = text[skills_match.end() : skills_match.end() + 500]
        for token in re.split(r"[,|•·\n/]", section):
            token = token.strip()
            if 2 <= len(token) <= 30 and not token.endswith(":"):
                if token not in found and token[0].isalpha():
                    found.append(token)
    return found[:25]


def _extract_summary(lines: list[str]) -> str | None:
    for idx, line in enumerate(lines):
        if SECTION_HEADERS["summary"].match(line.strip()):
            chunk = []
            for follow in lines[idx + 1 : idx + 6]:
                follow = follow.strip()
                if not follow or any(h.match(follow) for h in SECTION_HEADERS.values()):
                    break
                chunk.append(follow)
            if chunk:
                return " ".join(chunk)
    for line in lines[1:6]:
        line = line.strip()
        if len(line) > 40 and not EMAIL_RE.search(line) and not URL_RE.search(line):
            return line
    return None


def _extract_experience(text: str) -> list[WorkExperience]:
    experiences: list[WorkExperience] = []
    date_pattern = re.compile(
        r"(?P<title>[A-Za-z0-9\s/&,-]{3,60})\s+"
        r"(?P<company>[A-Za-z0-9\s.&,-]{2,50})\s+"
        r"(?P<dates>(?:\d{4}|Present|Current)[\s\-–—/to]+(?:\d{4}|Present|Current)?)",
        re.I,
    )
    for match in date_pattern.finditer(text):
        experiences.append(
            WorkExperience(
                title=match.group("title").strip(),
                company=match.group("company").strip(),
                start_date=match.group("dates").split("-")[0].strip(),
                end_date=None,
            )
        )
        if len(experiences) >= 5:
            break
    return experiences


def _parse_with_openai(text: str, api_key: str, model: str) -> Resume | None:
    try:
        from openai import OpenAI
    except ImportError:
        return None

    client = OpenAI(api_key=api_key)
    prompt = f"""Extract structured resume data from this PDF text as JSON with fields:
name, email, phone, location, linkedin, github, website, summary, skills (array),
experience (array of {{company, title, start_date, end_date, highlights}}),
education (array of {{school, degree, end_date}}).

Resume text:
{text[:6000]}
"""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Return only valid JSON matching the resume schema."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if not content:
        return None
    data = json.loads(content)
    return Resume.model_validate(data)


def parse_pdf_resume(
    path: Path,
    cache_dir: Path | None = None,
    openai_api_key: str | None = None,
    openai_model: str = "gpt-4o-mini",
    use_openai: bool = True,
) -> Resume:
    if not path.exists():
        raise FileNotFoundError(f"Resume PDF not found: {path}")

    cache_dir = cache_dir or Path(".resume-agent/cache")
    key = _cache_key(path)
    cached = _load_cache(cache_dir, key)
    if cached:
        return cached

    text = extract_text_from_pdf(path)
    if not text:
        raise ValueError(f"Could not extract text from PDF: {path}. Try a text-based PDF.")

    if use_openai and openai_api_key:
        ai_resume = _parse_with_openai(text, openai_api_key, openai_model)
        if ai_resume and ai_resume.email:
            _save_cache(cache_dir, key, ai_resume)
            return ai_resume

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    email_match = EMAIL_RE.search(text)
    email = email_match.group(0) if email_match else "you@example.com"
    phone_match = PHONE_RE.search(text)
    linkedin_match = LINKEDIN_RE.search(text)
    github_match = GITHUB_RE.search(text)

    resume = Resume(
        name=_extract_name(lines, email if email != "you@example.com" else None),
        email=email,
        phone=phone_match.group(0).strip() if phone_match else None,
        linkedin=linkedin_match.group(1) if linkedin_match else None,
        github=github_match.group(1) if github_match else None,
        summary=_extract_summary(lines),
        skills=_extract_skills(text),
        experience=_extract_experience(text),
        education=[],
    )
    _save_cache(cache_dir, key, resume)
    return resume
