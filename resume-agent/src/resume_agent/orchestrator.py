from __future__ import annotations

from resume_agent.agents import get_agents, select_agent
from resume_agent.config import AgentConfig, load_config
from resume_agent.models.application import ApplicationStatus
from resume_agent.models.job import Job
from resume_agent.models.resume import Resume
from resume_agent.parsers.resume_parser import parse_resume
from resume_agent.search.job_search import JobSearchEngine
from resume_agent.storage.tracker import ApplicationTracker


class ResumeApplyOrchestrator:
    def __init__(self, config: AgentConfig | None = None):
        self.config = config or load_config()
        self.tracker = ApplicationTracker(self.config.data_dir / "applications.db")
        self.agents = get_agents(self.config)

    async def search_jobs(self, limit: int = 30) -> list[Job]:
        engine = JobSearchEngine(
            keywords=self.config.search_keywords,
            min_score=self.config.min_match_score,
        )
        jobs = await engine.search_all(limit=limit)
        self.tracker.save_jobs(jobs)
        return jobs

    async def apply_to_jobs(
        self,
        jobs: list[Job] | None = None,
        resume: Resume | None = None,
    ) -> list:
        if resume is None:
            resume = parse_resume(self.config.resume_path)

        if jobs is None:
            jobs = await self.search_jobs(limit=self.config.max_applications_per_run * 3)

        results = []
        applied_count = 0

        for job in jobs:
            if applied_count >= self.config.max_applications_per_run:
                break

            if job.company.lower() in {c.lower() for c in self.config.exclude_companies}:
                continue

            if self.tracker.has_applied(job.id):
                continue

            agent = await select_agent(self.agents, job)
            cover_letter = agent.build_cover_letter(job, resume)
            result = await agent.apply(job, resume, cover_letter)
            application = agent.to_application(job, result, cover_letter)
            self.tracker.save_application(application)
            results.append(application)

            if result.status in {ApplicationStatus.APPLIED, ApplicationStatus.PENDING}:
                applied_count += 1

        return results

    def get_status(self) -> dict:
        stats = self.tracker.stats()
        recent = self.tracker.list_applications()[:10]
        return {"stats": stats, "recent": recent}
