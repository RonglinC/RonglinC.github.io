from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from resume_agent.models.resume import Resume


class AgentConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    resume_path: Path = Path("resume.pdf")
    resume_pdf_path: Path | None = None
    data_dir: Path = Path(".resume-agent")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = "gpt-4o-mini"
    headless: bool = True
    dry_run: bool = False
    max_applications_per_run: int = 10
    search_keywords: list[str] = Field(default_factory=lambda: ["software engineer", "full stack"])
    search_locations: list[str] = Field(default_factory=lambda: ["remote"])
    exclude_companies: list[str] = Field(default_factory=list)
    min_match_score: float = 0.3
    tailor_cover_letter: bool = True
    auto_submit: bool = False


def load_resume(path: Path) -> Resume:
    if not path.exists():
        raise FileNotFoundError(f"Resume not found: {path}")

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return Resume.model_validate(data)


def resolve_config(config: AgentConfig) -> AgentConfig:
    """Ensure PDF upload path is set when the primary resume is a PDF."""
    if config.resume_path.suffix.lower() == ".pdf":
        if config.resume_pdf_path is None:
            config.resume_pdf_path = config.resume_path
    elif config.resume_pdf_path is None:
        pdf_candidate = config.resume_path.with_suffix(".pdf")
        if pdf_candidate.exists():
            config.resume_pdf_path = pdf_candidate
    return config


def load_config(config_path: Path | None = None) -> AgentConfig:
    if config_path and config_path.exists():
        with config_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return resolve_config(AgentConfig(**data))
    return resolve_config(AgentConfig())
