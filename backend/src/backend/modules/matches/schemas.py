import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, StringConstraints, model_validator

MatchStatus = Literal["pending", "completed", "failed"]
Verdict = Literal["strong", "partial", "missing"]

JD_MIN_LENGTH = 200
JD_MAX_LENGTH = 20000


class MatchCreate(BaseModel):
    """A job to check: its link, its description, or both. With only a link,
    the page is fetched and the description read from it.
    """

    jd_text: (
        Annotated[
            str,
            StringConstraints(
                strip_whitespace=True, min_length=JD_MIN_LENGTH, max_length=JD_MAX_LENGTH
            ),
        ]
        | None
    ) = None
    url: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    role: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None
    company: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None

    @model_validator(mode="after")
    def needs_a_link_or_a_description(self) -> Self:
        if not self.jd_text and not self.url:
            raise ValueError("Give the job's link or paste its description.")
        return self


class SkillResult(BaseModel):
    name: str
    required: bool
    verdict: Verdict
    evidence_label: str | None = None
    evidence_text: str | None = None
    reason: str | None = None


class ExperienceCheck(BaseModel):
    """Where the candidate stands on experience for this job. Always present on
    a completed check, including when the posting gives no number.
    """

    status: Literal["meets", "short", "well_short", "open_to_freshers", "not_stated"]
    required_min: float | None
    required_max: float | None
    candidate_years: float
    # "stated" in the posting, only "preferred", worked out from the "title", or "fresher".
    source: Literal["stated", "preferred", "title", "fresher"] | None
    # The posting's own words behind the number.
    quote: str | None
    summary: str
    # All years of work, when `candidate_years` counts only the job's field.
    total_years: float | None = None


class FieldFitCheck(BaseModel):
    """The job's line of work against the ones the candidate has worked in."""

    status: Literal["same", "related", "different", "unknown"]
    job_field: str | None
    candidate_fields: list[str]
    summary: str


class ScoreLimit(BaseModel):
    """Something that held the score below what the skills alone earned."""

    kind: Literal["experience", "field", "must_have", "thin"]
    limit: int
    reason: str


class MatchRead(BaseModel):
    id: uuid.UUID
    status: MatchStatus
    error: str | None
    score: int | None
    raw_score: int | None
    seniority_note: str | None
    experience: ExperienceCheck | None
    # The most this job's score can be whatever skills are added (experience,
    # field, a missing licence...), or None when nothing limits it.
    score_cap: int | None = None
    # One sentence on why the score is what it is, for the top of every result.
    summary: str | None = None
    # The job is in a different line of work from the candidate's, so it was
    # answered from its title and must-haves without a full (model) read.
    screened: bool = False
    field_fit: FieldFitCheck | None = None
    # Why the score is below `raw_score`, one entry per limit that lowered it.
    limits: list[ScoreLimit] = []
    role: str | None
    company: str | None
    url: str | None
    # From the listing page, when the job was read from a link.
    location: str | None
    employment_type: str | None
    salary: str | None
    skill_results: list[SkillResult]
    gaps: list[str]
    profile_version: int
    created_at: datetime
