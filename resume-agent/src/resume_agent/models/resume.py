from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class WorkExperience(BaseModel):
    company: str
    title: str
    start_date: str
    end_date: str | None = None
    location: str | None = None
    highlights: list[str] = Field(default_factory=list)


class Education(BaseModel):
    school: str
    degree: str
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class Resume(BaseModel):
    name: str
    email: str
    phone: str | None = None
    location: str | None = None
    linkedin: HttpUrl | str | None = None
    github: HttpUrl | str | None = None
    website: HttpUrl | str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)

    def skills_text(self) -> str:
        return ", ".join(self.skills)

    def latest_title(self) -> str:
        if self.experience:
            return self.experience[0].title
        return "Software Engineer"
