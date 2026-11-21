from __future__ import annotations

import asyncio

from resume_agent.agents.base import ApplyResult, BaseApplyAgent
from resume_agent.models.application import ApplicationStatus
from resume_agent.models.job import Job
from resume_agent.models.resume import Resume
from resume_agent.search.job_search import detect_ats, extract_lever_slug


class LeverAgent(BaseApplyAgent):
    name = "lever"

    async def can_apply(self, job: Job) -> bool:
        url = str(job.apply_url or job.url)
        return detect_ats(url) == "lever" or extract_lever_slug(url) is not None

    async def apply(self, job: Job, resume: Resume, cover_letter: str) -> ApplyResult:
        url = str(job.apply_url or job.url)

        if self.config.dry_run:
            return ApplyResult(
                success=True,
                status=ApplicationStatus.SKIPPED,
                message=f"[DRY RUN] Would apply via Lever: {url}",
                cover_letter=cover_letter,
            )

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return ApplyResult(
                success=False,
                status=ApplicationStatus.FAILED,
                message="Playwright not installed. Run: playwright install chromium",
            )

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.config.headless)
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(1)

                apply_btn = page.locator('a.postings-btn, a:has-text("Apply")').first
                if await apply_btn.count() > 0:
                    await apply_btn.click()
                    await page.wait_for_timeout(1500)

                name_parts = resume.name.split(maxsplit=1)
                await self._fill(page, 'input[name="name"]', resume.name)
                await self._fill(page, 'input[name="email"]', resume.email)
                if resume.phone:
                    await self._fill(page, 'input[name="phone"]', resume.phone)
                if resume.linkedin:
                    await self._fill(page, 'input[name="urls[LinkedIn]"]', str(resume.linkedin))

                additional = page.locator('textarea[name="comments"], textarea').first
                if await additional.count() > 0:
                    await additional.fill(cover_letter)

                if self.config.resume_pdf_path and self.config.resume_pdf_path.exists():
                    file_input = page.locator('input[type="file"]').first
                    if await file_input.count() > 0:
                        await file_input.set_input_files(str(self.config.resume_pdf_path))

                if self.config.auto_submit:
                    submit = page.locator(
                        'button[type="submit"], .template-btn-submit'
                    ).first
                    if await submit.count() > 0:
                        await submit.click()
                        await page.wait_for_timeout(3000)
                        return ApplyResult(
                            success=True,
                            status=ApplicationStatus.APPLIED,
                            message="Application submitted via Lever",
                            cover_letter=cover_letter,
                        )
                    return ApplyResult(
                        success=True,
                        status=ApplicationStatus.PENDING,
                        message="Form filled but submit button not found",
                        cover_letter=cover_letter,
                    )

                return ApplyResult(
                    success=True,
                    status=ApplicationStatus.PENDING,
                    message="Form pre-filled — set auto_submit=true to submit",
                    cover_letter=cover_letter,
                )
            except Exception as exc:
                return ApplyResult(
                    success=False,
                    status=ApplicationStatus.FAILED,
                    message=f"Lever apply failed: {exc}",
                )
            finally:
                await browser.close()

    async def _fill(self, page, selector: str, value: str) -> None:
        locator = page.locator(selector).first
        if await locator.count() > 0:
            await locator.fill(value)
