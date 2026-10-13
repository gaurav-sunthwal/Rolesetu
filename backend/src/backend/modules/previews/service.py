"""Job previews for the landing page: what a job asks for, before signing in.

A visitor pastes a link and sees the job and the skills it wants. There is no
score, because there is no profile to score against yet. Nothing here calls a
model: the page is fetched and its skills are read with the local dictionary.
"""

import dataclasses
import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import urldefrag

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.exceptions import RateLimitedError
from backend.modules.matches.fetching.job_page import JobPage
from backend.modules.matches.fetching.reader import load_job_page
from backend.modules.matches.fetching.safe_fetch import PageFetchError
from backend.modules.matches.local.jd import parse_job
from backend.modules.previews import repository
from backend.modules.previews.models import JobPreview
from backend.modules.previews.schemas import JobPreviewRead

# New links one visitor can have read in an hour. A link already read is free.
MAX_PREVIEWS_PER_HOUR = 10
# How long a job read from a link is reused, for any visitor and for the check
# that follows once they sign in.
FRESH_FOR = timedelta(hours=24)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _url_hash(url: str) -> str:
    return _hash(urldefrag(url.strip()).url)


def _to_read(url: str, page: JobPage) -> JobPreviewRead:
    job = parse_job(page.as_text(), url=url)
    return JobPreviewRead(
        url=url,
        title=page.title or job.role,
        company=page.company or job.company,
        location=page.location,
        employment_type=page.employment_type,
        salary=page.salary,
        min_years_experience=job.min_years,
        required_skills=[item.name for item in job.requirements if item.required],
        nice_to_have_skills=[item.name for item in job.requirements if not item.required],
    )


async def fresh_page(db: AsyncSession, url: str, now: datetime) -> JobPage | None:
    """The job at this link if a preview read it recently, so it is not fetched twice."""
    row = await repository.find_fresh(db, _url_hash(url), now - FRESH_FOR)
    return JobPage(**row.page) if row is not None and row.page is not None else None


async def preview_job(db: AsyncSession, *, url: str, client_ip: str) -> JobPreviewRead:
    now = datetime.now(UTC)
    known = await fresh_page(db, url, now)
    if known is not None:
        return _to_read(url, known)

    client_hash = _hash(client_ip)
    recent = await repository.count_by_client(db, client_hash, now - timedelta(hours=1))
    if recent >= MAX_PREVIEWS_PER_HOUR:
        raise RateLimitedError(
            "You have looked up a lot of jobs in the last hour. "
            "Sign in to keep going, or try again a little later."
        )

    attempt = JobPreview(url_hash=_url_hash(url), client_hash=client_hash)

    async def within_budget() -> bool:
        used = await repository.count_rendered(db, now - timedelta(days=1))
        allowed = used < get_settings().preview_rendered_reads_per_day
        if allowed:
            # Recorded even if the read then fails: the credit is spent either way.
            attempt.reader = "rendered"
        return allowed

    try:
        page, attempt.reader = await load_job_page(url, within_budget)
    except PageFetchError:
        # Failed attempts count towards the limits too, so the row must outlive
        # the rollback that the error is about to cause.
        db.add(attempt)
        await db.commit()
        raise
    attempt.page = dataclasses.asdict(page)
    db.add(attempt)
    await repository.delete_older_than(db, now - FRESH_FOR)
    return _to_read(url, page)
