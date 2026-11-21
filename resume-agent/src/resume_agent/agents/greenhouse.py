from __future__ import annotations

import asyncio
import re

from resume_agent.agents.base import ApplyResult, BaseApplyAgent
from resume_agent.models.application import ApplicationStatus
from resume_agent.models.job import Job
from resume_agent.models.resume import Resume
from resume_agent.search.job_search import detect_ats, extract_greenhouse_board


class GreenhouseAgent(BaseApplyAgent):
    name = "greenhouse"

    async def can_apply(self, job: Job) -> bool:
        url = str(job.apply_url or job.url)
        return detect_ats(url) == "greenhouse" or extract_greenhouse_board(url) is not None

    async def apply(self, job: Job, resume: Resume, cover_letter: str) -> ApplyResult:
        url = str(job.apply_url or job.url)
        board_info = extract_greenhouse_board(url)

        if self.config.dry_run:
            return ApplyResult(
                success=True,
                status=ApplicationStatus.SKIPPED,
                message=f"[DRY RUN] Would apply via Greenhouse: {url}",
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

                await self._fill_field(page, ["first_name", "firstname"], resume.name.split()[0])
                if len(resume.name.split()) > 1:
                    await self._fill_field(
                        page,
                        ["last_name", "lastname"],
                        " ".join(resume.name.split()[1:]),
                    )
                await self._fill_field(page, ["email"], resume.email)
                if resume.phone:
                    await self._fill_field(page, ["phone"], resume.phone)

                if resume.linkedin:
                    await self._fill_field(page, ["linkedin", "urls[LinkedIn]"], str(resume.linkedin))

                await self._fill_textarea(page, cover_letter)

                if self.config.resume_pdf_path and self.config.resume_pdf_path.exists():
                    file_input = page.locator('input[type="file"]').first
                    if await file_input.count() > 0:
                        await file_input.set_input_files(str(self.config.resume_pdf_path))

                if self.config.auto_submit:
                    submit = page.locator(
                        'button[type="submit"], input[type="submit"], #submit_app'
                    ).first
                    if await submit.count() > 0:
                        await submit.click()
                        await page.wait_for_timeout(3000)
                        message = "Application submitted via Greenhouse"
                        status = ApplicationStatus.APPLIED
                    else:
                        message = "Form filled but submit button not found — review manually"
                        status = ApplicationStatus.PENDING
                else:
                    message = "Form pre-filled — set auto_submit=true to submit automatically"
                    status = ApplicationStatus.PENDING

                return ApplyResult(
                    success=True,
                    status=status,
                    message=message,
                    cover_letter=cover_letter,
                )
            except Exception as exc:
                return ApplyResult(
                    success=False,
                    status=ApplicationStatus.FAILED,
                    message=f"Greenhouse apply failed: {exc}",
                )
            finally:
                await browser.close()

    async def _fill_field(self, page, names: list[str], value: str) -> None:
        for name in names:
            selectors = [
                f'input[name="{name}"]',
                f'input[id="{name}"]',
                f'input[name*="{name}"]',
            ]
            for selector in selectors:
                locator = page.locator(selector).first
                if await locator.count() > 0 and await locator.is_visible():
                    await locator.fill(value)
                    return

    async def _fill_textarea(self, page, cover_letter: str) -> None:
        patterns = ["cover_letter", "cover letter", "why", "message"]
        for pattern in patterns:
            locator = page.locator(
                f'textarea[name*="{pattern}" i], textarea[id*="{pattern}" i]'
            ).first
            if await locator.count() > 0:
                await locator.fill(cover_letter)
                return

        textareas = page.locator("textarea")
        if await textareas.count() > 0:
            await textareas.last.fill(cover_letter)
