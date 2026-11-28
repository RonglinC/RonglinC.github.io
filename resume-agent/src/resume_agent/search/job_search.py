from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

import httpx

from resume_agent.models.job import Job, JobSource


def _job_id(source: JobSource, raw_id: str) -> str:
    return f"{source.value}:{raw_id}"


def _match_keywords(text: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    return hits / len(keywords)


class JobSearchEngine:
    def __init__(self, keywords: list[str] | None = None, min_score: float = 0.3):
        self.keywords = keywords or []
        self.min_score = min_score

    async def search_all(self, limit: int = 50) -> list[Job]:
        jobs: list[Job] = []
        async with httpx.AsyncClient(timeout=30) as client:
            remotive = await self._search_remotive(client)
            arbeitnow = await self._search_arbeitnow(client)
            jobs.extend(remotive)
            jobs.extend(arbeitnow)

        seen: set[str] = set()
        filtered: list[Job] = []
        for job in jobs:
            if job.id in seen:
                continue
            score = _match_keywords(
                f"{job.title} {job.description or ''} {' '.join(job.tags)}",
                self.keywords,
            )
            if score >= self.min_score:
                seen.add(job.id)
                filtered.append(job)

        def _sort_key(job: Job) -> datetime:
            if job.posted_at is None:
                return datetime.min.replace(tzinfo=timezone.utc)
            if job.posted_at.tzinfo is None:
                return job.posted_at.replace(tzinfo=timezone.utc)
            return job.posted_at

        filtered.sort(key=_sort_key, reverse=True)
        return filtered[:limit]

    async def _search_remotive(self, client: httpx.AsyncClient) -> list[Job]:
        response = await client.get("https://remotive.com/api/remote-jobs")
        response.raise_for_status()
        payload = response.json()
        jobs: list[Job] = []

        for item in payload.get("jobs", []):
            posted = item.get("publication_date")
            posted_at = None
            if posted:
                try:
                    posted_at = datetime.fromisoformat(posted.replace("Z", "+00:00"))
                except ValueError:
                    posted_at = None

            jobs.append(
                Job(
                    id=_job_id(JobSource.REMOTIVE, str(item["id"])),
                    title=item.get("title", "Unknown"),
                    company=item.get("company_name", "Unknown"),
                    url=item.get("url", ""),
                    apply_url=item.get("url", ""),
                    source=JobSource.REMOTIVE,
                    location=item.get("candidate_required_location"),
                    remote=True,
                    description=item.get("description"),
                    tags=item.get("tags", []) or [],
                    posted_at=posted_at,
                )
            )
        return jobs

    async def _search_arbeitnow(self, client: httpx.AsyncClient) -> list[Job]:
        response = await client.get("https://www.arbeitnow.com/api/job-board-api")
        response.raise_for_status()
        payload = response.json()
        jobs: list[Job] = []

        for item in payload.get("data", []):
            slug = item.get("slug", "")
            jobs.append(
                Job(
                    id=_job_id(JobSource.ARBEITNOW, slug or item.get("url", "")),
                    title=item.get("title", "Unknown"),
                    company=item.get("company_name", "Unknown"),
                    url=item.get("url", ""),
                    apply_url=item.get("url", ""),
                    source=JobSource.ARBEITNOW,
                    location=item.get("location"),
                    remote=bool(item.get("remote")),
                    description=item.get("description"),
                    tags=item.get("tags", []) or [],
                    posted_at=datetime.fromtimestamp(item["created_at"], tz=timezone.utc)
                    if item.get("created_at")
                    else None,
                )
            )
        return jobs


def detect_ats(url: str) -> str | None:
    url_lower = url.lower()
    if "greenhouse.io" in url_lower or "boards.greenhouse.io" in url_lower:
        return "greenhouse"
    if "jobs.lever.co" in url_lower or "lever.co" in url_lower:
        return "lever"
    if "myworkdayjobs.com" in url_lower:
        return "workday"
    if "ashbyhq.com" in url_lower:
        return "ashby"
    return None


def extract_greenhouse_board(url: str) -> tuple[str, str] | None:
    match = re.search(r"boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if match:
        return match.group(1), match.group(2)
    match = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if match:
        return match.group(1), match.group(2)
    return None


def extract_lever_slug(url: str) -> tuple[str, str] | None:
    match = re.search(r"jobs\.lever\.co/([^/]+)/([a-f0-9-]+)", url)
    if match:
        return match.group(1), match.group(2)
    return None


def stable_job_key(title: str, company: str, url: str) -> str:
    raw = f"{title}|{company}|{url}".lower()
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
