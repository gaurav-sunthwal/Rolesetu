"""Job previews: what a job asks for, before signing in.

A visitor pastes a link on the landing page, or opens a job with the extension
installed but not yet connected, and sees the job and the skills it wants. There
is no score, because there is no profile to score against yet. Nothing here
calls a model: the skills are read with the local dictionary.
"""

import dataclasses
import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import urldefrag, urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.client_ip import hash_ip
from backend.core.config import get_settings
from backend.core.exceptions import RateLimitedError
from backend.modules.matches.fetching.job_page import JobPage
from backend.modules.matches.fetching.reader import load_job_page
from backend.modules.matches.fetching.safe_fetch import PageFetchError
from backend.modules.matches.local.jd import parse_job
from backend.modules.previews import repository
from backend.modules.previews.models import JobPreview
from backend.modules.previews.repository import PAGE_TEXT
from backend.modules.previews.schemas import JobPreviewRead

# New links one visitor can have read in an hour. A link already read is free.
MAX_PREVIEWS_PER_HOUR = 10
# Jobs the extension can send as text in an hour. Nothing is fetched, so this is
# set for someone browsing a job board, far above the links limit.
MAX_TEXT_PREVIEWS_PER_HOUR = 60
# Shorter than this, the page showed only part of the job: the link is read instead.
MIN_DESCRIPTION = 200
# How long a job read from a link is reused, for any visitor and for the check
# that follows once they sign in.
FRESH_FOR = timedelta(hours=24)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _url_hash(url: str) -> str:
    return _hash(urldefrag(url.strip()).url)


def _host(url: str) -> str | None:
    host = urlsplit(url.strip()).hostname
    return host.removeprefix("www.").lower()[:120] if host else None


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


async def preview_job(
    db: AsyncSession,
    *,
    url: str,
    client_ip: str,
    description: str | None = None,
    title: str | None = None,
    company: str | None = None,
) -> JobPreviewRead:
    now = datetime.now(UTC)
    client_hash = hash_ip(client_ip)
    if description is not None and len(description) >= MIN_DESCRIPTION:
        page = JobPage(title=title, company=company, description=description, source="page text")
        return await _preview_text(db, url, page, client_hash, now)

    known = await fresh_page(db, url, now)
    if known is not None:
        return _to_read(url, known)

    recent = await repository.count_by_client(
        db, client_hash, now - timedelta(hours=1), page_text=False
    )
    if recent >= MAX_PREVIEWS_PER_HOUR:
        raise RateLimitedError(
            "You have looked up a lot of jobs in the last hour. "
            "Sign in to keep going, or try again a little later."
        )

    attempt = JobPreview(url_hash=_url_hash(url), client_hash=client_hash, host=_host(url))

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


async def _preview_text(
    db: AsyncSession, url: str, page: JobPage, client_hash: str, now: datetime
) -> JobPreviewRead:
    """The job as the visitor's own page shows it. It is not kept for anyone else:
    text sent by a visitor must never stand in for what the link really says."""
    recent = await repository.count_by_client(
        db, client_hash, now - timedelta(hours=1), page_text=True
    )
    if recent >= MAX_TEXT_PREVIEWS_PER_HOUR:
        raise RateLimitedError(
            "You have looked at a lot of jobs in the last hour. "
            "Connect your account to keep going, or try again a little later."
        )
    db.add(
        JobPreview(
            url_hash=_url_hash(url), client_hash=client_hash, host=_host(url), reader=PAGE_TEXT
        )
    )
    return _to_read(url, page)
