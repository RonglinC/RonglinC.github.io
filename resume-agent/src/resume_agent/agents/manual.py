from __future__ import annotations

from resume_agent.agents.base import ApplyResult, BaseApplyAgent
from resume_agent.models.application import ApplicationStatus
from resume_agent.models.job import Job
from resume_agent.models.resume import Resume


class ManualAgent(BaseApplyAgent):
    """Fallback agent: generates cover letter and records application for manual follow-up."""

    name = "manual"

    async def can_apply(self, job: Job) -> bool:
        return True

    async def apply(self, job: Job, resume: Resume, cover_letter: str) -> ApplyResult:
        url = str(job.apply_url or job.url)
        if self.config.dry_run:
            return ApplyResult(
                success=True,
                status=ApplicationStatus.SKIPPED,
                message=f"[DRY RUN] Manual apply link: {url}",
                cover_letter=cover_letter,
            )

        return ApplyResult(
            success=True,
            status=ApplicationStatus.PENDING,
            message=f"Cover letter generated. Apply manually at: {url}",
            cover_letter=cover_letter,
        )
