from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class JobSource(str, Enum):
    REMOTIVE = "remotive"
    ARBEITNOW = "arbeitnow"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    MANUAL = "manual"


class Job(BaseModel):
    id: str
    title: str
    company: str
    url: HttpUrl | str
    source: JobSource
    location: str | None = None
    remote: bool = False
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None
    apply_url: HttpUrl | str | None = None

    def display_name(self) -> str:
        return f"{self.title} @ {self.company}"
