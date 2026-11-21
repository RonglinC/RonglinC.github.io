from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from resume_agent.config import AgentConfig
from resume_agent.llm.tailor import generate_cover_letter
from resume_agent.models.application import Application, ApplicationStatus
from resume_agent.models.job import Job
from resume_agent.models.resume import Resume


@dataclass
class ApplyResult:
    success: bool
    status: ApplicationStatus
    message: str
    cover_letter: str | None = None


class BaseApplyAgent(ABC):
    name: str = "base"

    def __init__(self, config: AgentConfig):
        self.config = config

    @abstractmethod
    async def can_apply(self, job: Job) -> bool:
        ...

    @abstractmethod
    async def apply(self, job: Job, resume: Resume, cover_letter: str) -> ApplyResult:
        ...

    def build_cover_letter(self, job: Job, resume: Resume) -> str:
        if not self.config.tailor_cover_letter:
            return generate_cover_letter(resume, job, None, self.config.openai_model)
        return generate_cover_letter(
            resume,
            job,
            self.config.openai_api_key,
            self.config.openai_model,
        )

    def to_application(
        self,
        job: Job,
        result: ApplyResult,
        cover_letter: str | None = None,
    ) -> Application:
        return Application(
            job_id=job.id,
            job_title=job.title,
            company=job.company,
            job_url=str(job.url),
            status=result.status,
            applied_at=datetime.now(timezone.utc) if result.success else None,
            cover_letter=cover_letter,
            error=None if result.success else result.message,
            agent=self.name,
            notes=result.message,
        )
