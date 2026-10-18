from datetime import date, datetime

from pydantic import BaseModel, Field

from backend.modules.career_jobs.fit import FitKind
from backend.modules.matches.schemas import SkillResult


class CareerCompany(BaseModel):
    slug: str
    name: str
    # Jobs in India from the last collection; 0 also when it has not been read yet.
    job_count: int
    added: bool
    # The last read failed; its older jobs may still be listed.
    error: str | None


class CareerCompanyList(BaseModel):
    collected_at: datetime | None
    days: int
    companies: list[CareerCompany]


class CareerCompanyAdd(BaseModel):
    link: str = Field(min_length=8, max_length=500)


class CareerJobRead(BaseModel):
    id: str
    company_slug: str
    company: str
    title: str
    url: str
    location: str
    places: list[str]
    posted_on: date | None
    first_seen: date
    # None when the posting names no skill we recognise, so it cannot be scored.
    score: int | None
    fit: FitKind
    fit_note: str
    skill_results: list[SkillResult]


class PlaceCount(BaseModel):
    name: str
    count: int


class CareerJobPage(BaseModel):
    items: list[CareerJobRead]
    next_cursor: str | None
    # Jobs that pass every filter, across all pages.
    total: int
    # Every place the chosen companies' jobs are in, for the city filter.
    places: list[PlaceCount]
    collected_at: datetime | None
    # The user's experience the list was filtered by.
    candidate_years: float
