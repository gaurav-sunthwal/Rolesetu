"""Jobs collected from company careers sites.

These rows are not anyone's own data: they are public job listings, read once
a day and shared by every user. Which jobs a user sees is decided when they
are listed (by experience and their own filters), not by who owns a row.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin


class CareerCompany(TimestampMixin, Base):
    """A company whose careers site is read, from the catalog or added by a user."""

    __tablename__ = "career_companies"
    __table_args__ = (Index("ix_career_companies_added_by_created", "added_by", "created_at"),)

    slug: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    # Which reader understands the site (workday, greenhouse, ...), and its settings.
    kind: Mapped[str] = mapped_column(String(40))
    config: Mapped[dict[str, str]] = mapped_column(JSONB)
    added: Mapped[bool] = mapped_column(default=False)
    # Who added it, kept to limit how many sites one person can add.
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    # Why the last read failed, in a few words; None when it worked.
    error: Mapped[str | None] = mapped_column(String(200), default=None)


class CareerJob(Base):
    __tablename__ = "career_jobs"
    __table_args__ = (Index("ix_career_jobs_company_slug", "company_slug"),)

    # "<company slug>:<the site's own id>", stable from one collection to the next.
    id: Mapped[str] = mapped_column(String(300), primary_key=True)
    company_slug: Mapped[str] = mapped_column(
        String(80), ForeignKey("career_companies.slug", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(2000))
    location: Mapped[str] = mapped_column(String(300))
    places: Mapped[list[str]] = mapped_column(ARRAY(String(80)))
    posted_on: Mapped[date | None] = mapped_column(Date, default=None)
    first_seen: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text)
    min_years: Mapped[float | None] = mapped_column(Float, default=None)
    max_years: Mapped[float | None] = mapped_column(Float, default=None)
    experience_source: Mapped[str | None] = mapped_column(String(40), default=None)
    experience_quote: Mapped[str | None] = mapped_column(String(300), default=None)


class CareerCollector(Base):
    """One row: when jobs were last collected, and who is collecting now.

    `lease_until` is the lock. A server takes it by moving it forward only when
    it has passed, in one UPDATE, so two servers never collect at once. It works
    through a connection pooler, where a Postgres advisory lock would not.
    """

    __tablename__ = "career_collector"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Goes up on every change to the jobs, so a list built from them can be cached.
    version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
