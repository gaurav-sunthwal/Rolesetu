from datetime import date

from pydantic import BaseModel, Field


class ActivityDay(BaseModel):
    date: date
    applications: int = 0
    job_checks: int = 0
    extension: int = Field(default=0, description="Scores on job sites, autofill, saved answers.")
    ai: int = Field(default=0, description="AI answers and resume-assistant messages.")

    @property
    def total(self) -> int:
        return self.applications + self.job_checks + self.extension + self.ai


class Streaks(BaseModel):
    current: int = Field(description="Days in a row with activity, up to today (or yesterday).")
    longest: int
    active_days: int


class ActivityYear(BaseModel):
    """One user's activity per day over the last year, oldest first, every day listed."""

    start: date
    end: date
    timezone: str
    days: list[ActivityDay]
    totals: ActivityDay = Field(description="The year added up; its `date` is `end`.")
    streaks: Streaks
