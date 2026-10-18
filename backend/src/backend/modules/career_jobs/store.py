"""The collected jobs, kept in Postgres and shared by every API server.

Each company is saved on its own as soon as it has been read, so a user adding
a company and the daily collection can run side by side without one undoing
the other. Every change bumps a version number, which is what lets a server
keep the whole collection in memory between changes: it only has to ask the
database whether the version moved.
"""

import uuid
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.career_jobs.models import CareerCollector, CareerCompany, CareerJob

# Jobs older than this are dropped: the page is about what is new.
KEEP_DAYS = 7
_COLLECTOR_ID = 1


class StoredCompany(BaseModel):
    slug: str
    name: str
    kind: str
    config: dict[str, str]
    # Added by a user from a careers link, rather than from the catalog.
    added: bool = False
    # Why the last read failed, in a few words; None when it worked.
    error: str | None = None


class StoredJob(BaseModel):
    id: str
    company_slug: str
    title: str
    url: str
    location: str
    places: list[str]
    posted_on: date | None
    first_seen: date
    description: str
    min_years: float | None
    max_years: float | None
    experience_source: str | None
    experience_quote: str | None


class Collection(BaseModel):
    """Everything collected, as one server holds it in memory."""

    version: int = 0
    collected_at: datetime | None = None
    days: int = KEEP_DAYS
    companies: list[StoredCompany] = []
    jobs: list[StoredJob] = []


# This server's copy of the collection. Only a hint: it is checked against the
# database's version before use, so another server's changes are never missed.
_held: Collection | None = None


def _company(row: CareerCompany) -> StoredCompany:
    return StoredCompany(
        slug=row.slug,
        name=row.name,
        kind=row.kind,
        config=dict(row.config),
        added=row.added,
        error=row.error,
    )


def _job(row: CareerJob) -> StoredJob:
    return StoredJob(
        id=row.id,
        company_slug=row.company_slug,
        title=row.title,
        url=row.url,
        location=row.location,
        places=list(row.places),
        posted_on=row.posted_on,
        first_seen=row.first_seen,
        description=row.description,
        min_years=row.min_years,
        max_years=row.max_years,
        experience_source=row.experience_source,
        experience_quote=row.experience_quote,
    )


def _row(job: StoredJob) -> dict[str, Any]:
    """A job as a row, cut to the column sizes so one long field never fails a save."""
    return {
        "id": job.id[:300],
        "company_slug": job.company_slug,
        "title": job.title[:300],
        "url": job.url[:2000],
        "location": job.location[:300],
        "places": [place[:80] for place in job.places],
        "posted_on": job.posted_on,
        "first_seen": job.first_seen,
        "description": job.description,
        "min_years": job.min_years,
        "max_years": job.max_years,
        "experience_source": job.experience_source,
        "experience_quote": job.experience_quote[:300] if job.experience_quote else None,
    }


async def version(db: AsyncSession) -> int:
    found = await db.scalar(
        select(CareerCollector.version).where(CareerCollector.id == _COLLECTOR_ID)
    )
    return found or 0


async def companies(db: AsyncSession) -> list[StoredCompany]:
    rows = await db.scalars(select(CareerCompany))
    return [_company(row) for row in rows]


async def job_counts(db: AsyncSession) -> dict[str, int]:
    rows = await db.execute(
        select(CareerJob.company_slug, func.count()).group_by(CareerJob.company_slug)
    )
    return {slug: count for slug, count in rows.tuples()}


async def jobs_of(db: AsyncSession, slugs: Iterable[str]) -> list[StoredJob]:
    rows = await db.scalars(select(CareerJob).where(CareerJob.company_slug.in_(list(slugs))))
    return [_job(row) for row in rows]


async def current(db: AsyncSession) -> Collection:
    """The whole collection. Read from the database only when it has changed."""
    global _held
    collector = await db.scalar(select(CareerCollector).where(CareerCollector.id == _COLLECTOR_ID))
    now_version = collector.version if collector else 0
    if _held is not None and _held.version == now_version:
        return _held
    jobs = [_job(row) for row in await db.scalars(select(CareerJob))]
    _held = Collection(
        version=now_version,
        collected_at=collector.last_finished_at if collector else None,
        companies=await companies(db),
        jobs=jobs,
    )
    return _held


async def _bump(db: AsyncSession) -> None:
    await db.execute(
        update(CareerCollector)
        .where(CareerCollector.id == _COLLECTOR_ID)
        .values(version=CareerCollector.version + 1)
    )


async def save_company(
    db: AsyncSession,
    company: StoredCompany,
    jobs: list[StoredJob] | None,
    *,
    added_by: uuid.UUID | None = None,
) -> None:
    """Saves one company's read. `jobs` replaces its jobs; None (a failed read)
    keeps the jobs it had, so one bad morning does not empty a company."""
    values = {
        "slug": company.slug,
        "name": company.name[:120],
        "kind": company.kind,
        "config": company.config,
        "added": company.added,
        "added_by": added_by,
        "error": company.error[:200] if company.error else None,
    }
    statement = pg_insert(CareerCompany).values(**values)
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=[CareerCompany.slug],
            # Whoever added it first stays its owner; the rest follows the latest read.
            set_={
                "name": statement.excluded.name,
                "kind": statement.excluded.kind,
                "config": statement.excluded.config,
                "added": CareerCompany.added | statement.excluded.added,
                "error": statement.excluded.error,
                "updated_at": func.now(),
            },
        )
    )
    if jobs is not None:
        await db.execute(delete(CareerJob).where(CareerJob.company_slug == company.slug))
        if jobs:
            await db.execute(insert(CareerJob), [_row(job) for job in jobs])
    await _bump(db)


async def prune(db: AsyncSession, since: date) -> int:
    """Drops jobs first seen and posted before `since`."""
    result = await db.execute(
        delete(CareerJob).where(func.coalesce(CareerJob.posted_on, CareerJob.first_seen) < since)
    )
    dropped: int = getattr(result, "rowcount", 0) or 0
    if dropped:
        await _bump(db)
    return dropped


async def added_by_since(db: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    found = await db.scalar(
        select(func.count())
        .select_from(CareerCompany)
        .where(CareerCompany.added_by == user_id, CareerCompany.created_at > since)
    )
    return found or 0


async def added_total(db: AsyncSession) -> int:
    found = await db.scalar(
        select(func.count()).select_from(CareerCompany).where(CareerCompany.added.is_(True))
    )
    return found or 0


async def is_due(db: AsyncSession, every: timedelta) -> bool:
    last = await db.scalar(
        select(CareerCollector.last_finished_at).where(CareerCollector.id == _COLLECTOR_ID)
    )
    return last is None or last < datetime.now(last.tzinfo) - every


async def take_lease(db: AsyncSession, length: timedelta) -> bool:
    """Becomes the one server collecting, if no other is. True when taken."""
    taken = await db.scalar(
        update(CareerCollector)
        .where(
            CareerCollector.id == _COLLECTOR_ID,
            (CareerCollector.lease_until.is_(None)) | (CareerCollector.lease_until < func.now()),
        )
        .values(lease_until=func.now() + length)
        .returning(CareerCollector.id)
    )
    return taken is not None


async def finish(db: AsyncSession) -> None:
    await db.execute(
        update(CareerCollector)
        .where(CareerCollector.id == _COLLECTOR_ID)
        .values(last_finished_at=func.now(), lease_until=None, version=CareerCollector.version + 1)
    )


async def release(db: AsyncSession) -> None:
    await db.execute(
        update(CareerCollector).where(CareerCollector.id == _COLLECTOR_ID).values(lease_until=None)
    )
