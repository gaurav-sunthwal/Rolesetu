from datetime import date, datetime

from pydantic import BaseModel, Field

from backend.modules.career_jobs.fit import FitKind
from backend.modules.career_jobs.work_mode import WorkMode
from backend.modules.matches.schemas import SkillResult, Verdict


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


class ScoreBoost(BaseModel):
    """One skill that would raise this job's score if the user showed strong evidence for it."""

    name: str
    required: bool
    # Where the skill stands now: "partial" or "missing".
    verdict: Verdict
    # How many points the score would rise, worked out with the same maths as the score.
    points: int


class CareerJobRead(BaseModel):
    id: str
    company_slug: str
    company: str
    title: str
    url: str
    location: str
    places: list[str]
    work_mode: WorkMode
    posted_on: date | None
    first_seen: date
    # None when the posting names no skill we recognise, so it cannot be scored.
    score: int | None
    # The highest score experience allows for this job, or None when it does not limit it.
    score_cap: int | None
    fit: FitKind
    fit_note: str
    skill_results: list[SkillResult]
    # Biggest first; empty when no skill would raise the score.
    score_boosts: list[ScoreBoost]


class PlaceCount(BaseModel):
    name: str
    count: int


class WorkModeCount(BaseModel):
    mode: WorkMode
    count: int


class CareerJobPage(BaseModel):
    items: list[CareerJobRead]
    next_cursor: str | None
    # Jobs that pass every filter, across all pages.
    total: int
    # Every place the chosen companies' jobs are in, for the city filter.
    places: list[PlaceCount]
    # Every work mode among the chosen companies' jobs (in the chosen cities), for its filter.
    work_modes: list[WorkModeCount]
    collected_at: datetime | None
    # The user's experience the list was filtered by.
    candidate_years: float
    # How much of the current collection has been scored, 0 to 100.
    # 100 only when `items` is that finished list.
    scored_percent: int = Field(ge=0, le=100)
    # True while `items` is an older list for this profile and a newer one is still scoring.
    refreshing: bool
