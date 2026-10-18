"""The daily run: read every company, fill in each job's text, save.

    uv run python -m backend.modules.career_jobs.collect
    uv run python -m backend.modules.career_jobs.collect --only amazon google --max-per-company 100

In production the API runs this itself once a day (see `schedule.py`). Only
jobs not already saved are read in full, so a second run the same week costs
a fraction of the first.
"""

import argparse
import asyncio
import logging
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.exc import SQLAlchemyError

from backend.db.session import get_engine, get_sessionmaker
from backend.modules.career_jobs import store
from backend.modules.career_jobs.audience import EVERYONE, Audience
from backend.modules.career_jobs.catalog import COMPANIES
from backend.modules.career_jobs.places import filter_places
from backend.modules.career_jobs.repository import load_audience
from backend.modules.career_jobs.sources import build_reader
from backend.modules.career_jobs.sources.base import Http, Posting, new_client
from backend.modules.career_jobs.store import StoredCompany, StoredJob
from backend.modules.matches.local.experience import read_experience

logger = logging.getLogger(__name__)

DAYS = store.KEEP_DAYS
# Jobs read in full at once, across all companies (each site has its own limit too).
_IN_FLIGHT = 16
# The longest description kept; the same limit a job check accepts.
_MAX_DESCRIPTION = 20_000


def catalog_companies() -> list[StoredCompany]:
    return [
        StoredCompany(slug=c.slug, name=c.name, kind=c.kind, config=c.config) for c in COMPANIES
    ]


def _stored(company: StoredCompany, posting: Posting, first_seen: date) -> StoredJob | None:
    # The link is shown to users as "Open job", so only a web address is kept.
    if not posting.url.startswith(("https://", "http://")):
        return None
    description = (posting.description or "")[:_MAX_DESCRIPTION]
    asked = read_experience(description, posting.title)
    return StoredJob(
        id=f"{company.slug}:{posting.source_id}",
        company_slug=company.slug,
        title=posting.title,
        url=posting.url,
        location=posting.location,
        places=filter_places(posting.location),
        posted_on=posting.posted_on,
        first_seen=first_seen,
        description=description,
        min_years=asked.min_years,
        max_years=asked.max_years,
        experience_source=asked.source,
        experience_quote=asked.quote,
    )


@dataclass
class CompanyRead:
    jobs: list[StoredJob]
    # Jobs left out because no current user's experience band would see them.
    skipped: int


def _wanted(audience: Audience, title: str, description: str = "") -> bool:
    asked = read_experience(description, title)
    return audience.wants(min_years=asked.min_years, source=asked.source)


async def read_company(
    http: Http,
    company: StoredCompany,
    *,
    since: date,
    known: dict[str, StoredJob],
    audience: Audience = EVERYONE,
    max_jobs: int | None = None,
) -> CompanyRead:
    """This company's recent jobs in India for the users we have. Jobs in
    `known` are reused, not read again."""
    reader = build_reader(company.kind, company.config)
    postings = await reader.recent(http, since)
    # A title like "Senior Manager" already rules a job out; skip it before reading it.
    listed = len(postings)
    postings = [p for p in postings if _wanted(audience, p.title)]
    skipped_by_title = listed - len(postings)
    postings.sort(key=lambda p: p.posted_on or date.max, reverse=True)
    if max_jobs is not None:
        postings = postings[:max_jobs]
    today = date.today()
    gate = asyncio.Semaphore(_IN_FLIGHT)

    async def one(posting: Posting) -> StoredJob | None:
        previous = known.get(f"{company.slug}:{posting.source_id}")
        if previous is not None and previous.description:
            return previous
        async with gate:
            try:
                complete = await reader.complete(http, posting)
            except Exception as exc:  # One unreadable job must not lose the company.
                logger.warning(
                    "career job not read company=%s id=%s error=%s",
                    company.slug,
                    posting.source_id,
                    type(exc).__name__,
                )
                return None
        if complete is None or not complete.description:
            return None
        return _stored(company, complete, today)

    read = [job for job in await asyncio.gather(*(one(p) for p in postings)) if job]
    # The full text can say what the title did not ("8+ years").
    jobs = [
        job for job in read if audience.wants(min_years=job.min_years, source=job.experience_source)
    ]
    return CompanyRead(jobs=jobs, skipped=skipped_by_title + len(read) - len(jobs))


@dataclass
class Collected:
    """What a run read: each company as saved, and the jobs of those read well."""

    companies: dict[str, StoredCompany] = field(default_factory=dict)
    jobs: dict[str, list[StoredJob]] = field(default_factory=dict)
    skipped: int = 0


async def collect(
    companies: Iterable[StoredCompany],
    *,
    audience: Audience = EVERYONE,
    days: int = DAYS,
    max_per_company: int | None = None,
    report: bool = False,
    added_by: uuid.UUID | None = None,
    keep_failures: bool = True,
) -> Collected:
    """Reads `companies` and saves each one as soon as it is done; companies
    not in this run keep what they had. A company that cannot be read keeps
    its older jobs and is saved with the error, unless `keep_failures` is off
    (a user's new company that does not work is not kept at all)."""
    chosen = list(companies)
    since = date.today() - timedelta(days=days)
    sessions = get_sessionmaker()
    async with sessions() as db:
        known = {job.id: job for job in await store.jobs_of(db, [c.slug for c in chosen])}
    result = Collected()
    if report:
        print(audience.describe(), flush=True)

    async def save(company: StoredCompany, jobs: list[StoredJob] | None) -> None:
        async with sessions() as db:
            await store.save_company(db, company, jobs, added_by=added_by)
            await db.commit()

    async with new_client() as client:
        http = Http(client)
        sites = asyncio.Semaphore(6)

        async def run(company: StoredCompany) -> None:
            started = time.monotonic()
            async with sites:
                try:
                    read = await read_company(
                        http,
                        company,
                        since=since,
                        known=known,
                        audience=audience,
                        max_jobs=max_per_company,
                    )
                except Exception as exc:  # Its old jobs stay; the error is shown.
                    failed = company.model_copy(
                        update={"error": f"{type(exc).__name__}: {str(exc)[:160]}"}
                    )
                    result.companies[company.slug] = failed
                    logger.warning(
                        "careers site not read company=%s error=%s",
                        company.slug,
                        type(exc).__name__,
                    )
                    if keep_failures:
                        await save(failed, None)
                    if report:
                        print(f"✗ {company.name:24} {type(exc).__name__}", flush=True)
                    return
            done = company.model_copy(update={"error": None})
            await save(done, read.jobs)
            result.companies[company.slug] = done
            result.jobs[company.slug] = read.jobs
            result.skipped += read.skipped
            if report:
                took = time.monotonic() - started
                print(
                    f"✓ {company.name:24} {len(read.jobs):5} jobs "
                    f"({read.skipped} skipped) in {took:5.1f}s",
                    flush=True,
                )

        await asyncio.gather(*(run(c) for c in chosen))

    async with sessions() as db:
        await store.prune(db, since)
        await db.commit()
    if report:
        print(f"Skipped {result.skipped} jobs no current user's experience band would see.")
    return result


async def everyone_to_read() -> list[StoredCompany]:
    """The catalog, plus every company users added."""
    async with get_sessionmaker()() as db:
        added = [c for c in await store.companies(db) if c.added]
    return catalog_companies() + added


async def current_audience() -> Audience:
    """The users' bands, read once per run. If the database cannot be reached,
    everything is collected rather than nothing."""
    try:
        async with get_sessionmaker()() as db:
            return await load_audience(db)
    except (SQLAlchemyError, OSError) as exc:
        logger.warning("audience not read, collecting every level error=%s", type(exc).__name__)
        return EVERYONE


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="company slugs")
    parser.add_argument("--days", type=int, default=DAYS)
    parser.add_argument("--max-per-company", type=int, default=None)
    parser.add_argument(
        "--every-level", action="store_true", help="collect for every band, not only users'"
    )
    args = parser.parse_args()

    try:
        audience = EVERYONE if args.every_level else await current_audience()
        chosen = [c for c in await everyone_to_read() if not args.only or c.slug in args.only]
        result = await collect(
            chosen,
            audience=audience,
            days=args.days,
            max_per_company=args.max_per_company,
            report=True,
        )
    finally:
        await get_engine().dispose()
    saved = sum(len(jobs) for jobs in result.jobs.values())
    print(f"Saved {saved} jobs from {len(result.jobs)} of {len(result.companies)} companies.")


if __name__ == "__main__":
    asyncio.run(main())
