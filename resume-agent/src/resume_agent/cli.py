from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from resume_agent.config import load_config
from resume_agent.orchestrator import ResumeApplyOrchestrator
from resume_agent.parsers.resume_parser import parse_resume, resume_to_yaml
from resume_agent.models.resume import Resume, WorkExperience, Education

console = Console()


@click.group()
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def main(ctx: click.Context, config_path: Path | None) -> None:
    """Resume Agent — automated job search and application CLI."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config_path)


@main.command("init")
@click.option("--output", "-o", default="resume.yaml", help="Output resume file path")
def init_cmd(output: str) -> None:
    """Create a sample resume.yaml template."""
    sample = Resume(
        name="Your Name",
        email="you@example.com",
        phone="+1-555-0100",
        location="San Francisco, CA",
        linkedin="https://linkedin.com/in/yourprofile",
        github="https://github.com/yourusername",
        summary="Full-stack developer passionate about building reliable, user-focused products.",
        skills=["Python", "JavaScript", "React", "Node.js", "SQL", "AWS"],
        experience=[
            WorkExperience(
                company="Example Corp",
                title="Senior Software Engineer",
                start_date="2022-01",
                end_date="Present",
                location="Remote",
                highlights=[
                    "Led migration to microservices, reducing deploy time by 60%",
                    "Built React dashboard used by 10k+ daily active users",
                ],
            )
        ],
        education=[
            Education(
                school="University of Example",
                degree="B.S. Computer Science",
                end_date="2020",
            )
        ],
    )
    path = Path(output)
    path.write_text(resume_to_yaml(sample), encoding="utf-8")
    console.print(f"[green]Created sample resume:[/green] {path}")
    console.print("Edit this file with your details, then run: resume-agent search")


@main.command("search")
@click.option("--limit", default=20, help="Max jobs to return")
@click.pass_context
def search_cmd(ctx: click.Context, limit: int) -> None:
    """Search remote job boards for matching positions."""
    orchestrator = ResumeApplyOrchestrator(ctx.obj["config"])

    async def run():
        jobs = await orchestrator.search_jobs(limit=limit)
        table = Table(title=f"Found {len(jobs)} matching jobs")
        table.add_column("Title", style="cyan")
        table.add_column("Company")
        table.add_column("Source")
        table.add_column("URL", overflow="fold")

        for job in jobs:
            table.add_row(job.title, job.company, job.source.value, str(job.url))

        console.print(table)

    asyncio.run(run())


@main.command("apply")
@click.option("--limit", default=10, help="Max applications this run")
@click.option("--dry-run", is_flag=True, help="Preview without submitting")
@click.pass_context
def apply_cmd(ctx: click.Context, limit: int, dry_run: bool) -> None:
    """Search jobs and auto-apply using configured agents."""
    config = ctx.obj["config"]
    config.max_applications_per_run = limit
    if dry_run:
        config.dry_run = True

    orchestrator = ResumeApplyOrchestrator(config)

    async def run():
        try:
            resume = parse_resume(config.resume_path)
        except FileNotFoundError:
            console.print(
                "[red]Resume not found.[/red] Run [bold]resume-agent init[/bold] first."
            )
            return

        console.print(f"[bold]Applying as:[/bold] {resume.name} ({resume.email})")
        if config.dry_run:
            console.print("[yellow]DRY RUN mode — no forms will be submitted[/yellow]")

        results = await orchestrator.apply_to_jobs(resume=resume)
        table = Table(title=f"Processed {len(results)} applications")
        table.add_column("Job")
        table.add_column("Agent")
        table.add_column("Status")
        table.add_column("Notes", overflow="fold")

        for app in results:
            status_style = "green" if app.status.value == "applied" else "yellow"
            table.add_row(
                f"{app.job_title} @ {app.company}",
                app.agent or "-",
                f"[{status_style}]{app.status.value}[/{status_style}]",
                app.notes or app.error or "",
            )

        console.print(table)

    asyncio.run(run())


@main.command("status")
@click.pass_context
def status_cmd(ctx: click.Context) -> None:
    """Show application history and stats."""
    orchestrator = ResumeApplyOrchestrator(ctx.obj["config"])
    data = orchestrator.get_status()

    console.print("[bold]Application Stats[/bold]")
    for status, count in data["stats"].items():
        console.print(f"  {status}: {count}")

    if data["recent"]:
        table = Table(title="Recent Applications")
        table.add_column("Job")
        table.add_column("Status")
        table.add_column("Applied At")
        table.add_column("Agent")

        for app in data["recent"]:
            applied = app.applied_at.strftime("%Y-%m-%d %H:%M") if app.applied_at else "-"
            table.add_row(
                f"{app.job_title} @ {app.company}",
                app.status.value,
                applied,
                app.agent or "-",
            )

        console.print(table)
    else:
        console.print("[dim]No applications yet. Run resume-agent apply[/dim]")


@main.command("cover-letter")
@click.argument("job_url")
@click.pass_context
def cover_letter_cmd(ctx: click.Context, job_url: str) -> None:
    """Generate a cover letter for a specific job URL."""
    from resume_agent.llm.tailor import generate_cover_letter
    from resume_agent.models.job import Job, JobSource
    from resume_agent.search.job_search import stable_job_key

    config = ctx.obj["config"]
    resume = parse_resume(config.resume_path)
    job = Job(
        id=stable_job_key("Custom", "Unknown", job_url),
        title="Position",
        company="Company",
        url=job_url,
        source=JobSource.MANUAL,
    )
    letter = generate_cover_letter(
        resume, job, config.openai_api_key, config.openai_model
    )
    console.print(letter)


if __name__ == "__main__":
    main()
