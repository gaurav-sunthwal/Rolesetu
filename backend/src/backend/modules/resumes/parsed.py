"""The raw result of reading a resume, before it is validated and tidied
(see `normalize.py`). Fields are optional because a parser may not find them.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ParsedSkill(BaseModel):
    name: str
    level: Literal["beginner", "intermediate", "advanced"] | None = None


class ParsedExperience(BaseModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    start: str | None = None
    end: str | None = None
    is_current: bool = False
    description: str | None = None


class ParsedProject(BaseModel):
    name: str | None = None
    tech: list[str] = Field(default_factory=list)
    description: str | None = None
    url: str | None = None


class ParsedEducation(BaseModel):
    school: str | None = None
    degree: str | None = None
    field: str | None = None
    start_year: int | None = None
    end_year: int | None = None


class ParsedResume(BaseModel):
    full_name: str | None = None
    headline: str | None = None
    location: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    skills: list[ParsedSkill] = Field(default_factory=list)
    experience: list[ParsedExperience] = Field(default_factory=list)
    projects: list[ParsedProject] = Field(default_factory=list)
    education: list[ParsedEducation] = Field(default_factory=list)
