from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ApplicationStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    SKIPPED = "skipped"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    OFFER = "offer"


class Application(BaseModel):
    job_id: str
    job_title: str
    company: str
    job_url: str
    status: ApplicationStatus = ApplicationStatus.PENDING
    applied_at: datetime | None = None
    notes: str | None = None
    cover_letter: str | None = None
    error: str | None = None
    agent: str | None = None
    metadata: dict = Field(default_factory=dict)
