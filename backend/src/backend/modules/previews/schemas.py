from typing import Annotated

from pydantic import BaseModel, StringConstraints


class JobPreviewCreate(BaseModel):
    url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class JobPreviewRead(BaseModel):
    """What a job asks for, read from its link. No score: that needs a profile."""

    url: str
    title: str | None
    company: str | None
    location: str | None
    employment_type: str | None
    salary: str | None
    min_years_experience: int | None
    required_skills: list[str]
    nice_to_have_skills: list[str]
