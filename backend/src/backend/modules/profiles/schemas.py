from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
ItemId = Annotated[str, StringConstraints(min_length=1, max_length=64)]
YearMonth = Annotated[str, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


class Links(BaseModel):
    linkedin: Annotated[str, StringConstraints(max_length=300)] | None = None
    github: Annotated[str, StringConstraints(max_length=300)] | None = None
    portfolio: Annotated[str, StringConstraints(max_length=300)] | None = None


class SkillItem(BaseModel):
    id: ItemId
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    level: Literal["beginner", "intermediate", "advanced"] | None = None


class ExperienceItem(BaseModel):
    id: ItemId
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    company: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    location: ShortText | None = None
    # None when the date is not known.
    start: YearMonth | None = None
    # None means "present".
    end: YearMonth | None = None
    description: LongText = ""


class ProjectItem(BaseModel):
    id: ItemId
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    tech: list[Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]] = Field(
        default=[], max_length=25
    )
    description: LongText = ""
    url: Annotated[str, StringConstraints(max_length=300)] | None = None


class EducationItem(BaseModel):
    id: ItemId
    school: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    degree: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    field: ShortText | None = None
    start_year: int | None = Field(default=None, ge=1950, le=2100)
    end_year: int | None = Field(default=None, ge=1950, le=2100)


class ProfileWrite(BaseModel):
    full_name: ShortText | None = None
    headline: ShortText | None = None
    location: ShortText | None = None
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    links: Links = Field(default_factory=Links)
    skills: list[SkillItem] = Field(default_factory=list, max_length=100)
    experience: list[ExperienceItem] = Field(default_factory=list, max_length=30)
    projects: list[ProjectItem] = Field(default_factory=list, max_length=30)
    education: list[EducationItem] = Field(default_factory=list, max_length=10)


class ProfileRead(BaseModel):
    """Every field is always present in a response, so nothing is optional here."""

    full_name: str | None
    headline: str | None
    location: str | None
    phone: str | None
    links: Links
    skills: list[SkillItem]
    experience: list[ExperienceItem]
    projects: list[ProjectItem]
    education: list[EducationItem]
    version: int
    completeness: int = Field(ge=0, le=100)
    updated_at: datetime | None
