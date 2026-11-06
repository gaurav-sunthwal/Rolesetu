"""Picks and scores the collected jobs for one user.

Every job passes the experience rule first (cheap), then is scored by the local
engine (no model call). Scores are kept per (user, profile version, collection
version) so paging and changing filters do not score again. That cache is only
a per-server shortcut: its key includes the collection's version in the
database, so a change made through another server is never missed.

A new collection is scored in the background. Until it finishes, the page is
the last finished list for this same profile version, with a percent of how
far the new scoring has got. The user can open those jobs while the new ones
are still being matched.
"""

import asyncio
import base64
import binascii
import logging
import re
import uuid
from collections import Counter, OrderedDict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import RateLimitedError, ValidationFailedError
from backend.modules.career_jobs import store
from backend.modules.career_jobs.collect import DAYS, catalog_companies, collect
from backend.modules.career_jobs.detect import detect_source
from backend.modules.career_jobs.fit import fit_for
from backend.modules.career_jobs.places import REMOTE
from backend.modules.career_jobs.repository import load_audience, same_job, tracked_urls
from backend.modules.career_jobs.schemas import (
    CareerCompany,
    CareerCompanyList,
    CareerJobPage,
    CareerJobRead,
    PlaceCount,
    ScoreBoost,
    WorkModeCount,
)
from backend.modules.career_jobs.store import StoredCompany, StoredJob
from backend.modules.career_jobs.work_mode import WorkMode, work_mode_of
from backend.modules.matches import scoring
from backend.modules.matches.local.engine import score_locally
from backend.modules.matches.schemas import SkillResult
from backend.modules.profiles.schemas import ProfileRead
from backend.modules.profiles.service import get_profile

logger = logging.getLogger(__name__)

# A user's scored list, kept for the last few users who opened the page.
_CACHE_SIZE = 32
_cache: OrderedDict[tuple[uuid.UUID, int, int], list[CareerJobRead]] = OrderedDict()
# The last finished list for a user and profile version, kept so a new
# collection can be scored without hiding the jobs they already had.
_previous: dict[tuple[uuid.UUID, int], list[CareerJobRead]] = {}
# Skills a posting must name, that we recognise, for its score to rank on its own.
WELL_EVIDENCED = 3


@dataclass
class _Run:
    """One in-progress scoring of a collection for one profile."""

    done: int
    total: int
    # Jobs scored so far, replaced as a whole so the page can read it safely.
    shown: list[CareerJobRead] | None = None
    task: asyncio.Task[None] | None = None


# Scoring that has started and not finished, keyed like `_cache`.
_runs: dict[tuple[uuid.UUID, int, int], _Run] = {}


def invalidate_user_cache(user_id: uuid.UUID) -> None:
    """Drop all cached scores for a user so the next page scores fresh.

    Called when the user's profile changes, so that fresh jobs are re-scored
    against the new profile instead of serving stale results from the old one.
    """
    stale = [key for key in _cache if key[0] == user_id]
    for key in stale:
        del _cache[key]
    stale_prev = [key for key in _previous if key[0] == user_id]
    for key in stale_prev:
        del _previous[key]
    # Cancel any in-progress scoring too.
    stale_runs = [key for key in _runs if key[0] == user_id]
    for key in stale_runs:
        run = _runs.pop(key, None)
        if run and run.task:
            run.task.cancel()


# Reading a newly added company: one board API call, or a small Workday site.
ADD_TIMEOUT_SECONDS = 90
# Each added site is read every day for everyone, so adding is limited.
MAX_ADDS_PER_DAY = 5
MAX_ADDED_COMPANIES = 300


async def _companies(db: AsyncSession) -> dict[str, StoredCompany]:
    """The catalog plus companies users added, with each one's last read."""
    saved = {c.slug: c for c in await store.companies(db)}
    return {c.slug: saved.get(c.slug, c) for c in catalog_companies()} | {
        slug: c for slug, c in saved.items() if c.added
    }


async def list_companies(db: AsyncSession) -> CareerCompanyList:
    collection = await store.current(db)
    counts = Counter(job.company_slug for job in collection.jobs)
    companies = sorted((await _companies(db)).values(), key=lambda c: c.name.lower())
    return CareerCompanyList(
        collected_at=collection.collected_at,
        days=collection.days,
        companies=[
            CareerCompany(
                slug=c.slug,
                name=c.name,
                job_count=counts[c.slug],
                added=c.added,
                error=c.error,
            )
            for c in companies
        ],
    )


async def add_company(db: AsyncSession, link: str, *, user_id: uuid.UUID) -> CareerCompany:
    detected = detect_source(link)
    if detected is None:
        raise ValidationFailedError(
            "We can't read that careers site yet. Paste the link to the company's jobs page "
            "if it is hosted on Workday, Greenhouse, Lever, Ashby or SmartRecruiters "
            "(the address usually contains one of those names)."
        )
    token = re.sub(r"[^a-z0-9]+", "-", "-".join(detected.config.values()).lower()).strip("-")
    slug = f"{detected.kind}-{token}"[:80]
    # The same careers site may already be in the catalog under its own name.
    existing = next(
        (
            c
            for c in (await _companies(db)).values()
            if c.slug == slug or (c.kind == detected.kind and c.config == detected.config)
        ),
        None,
    )
    if existing is not None:
        jobs = (await store.job_counts(db)).get(existing.slug, 0)
        return CareerCompany(
            slug=existing.slug,
            name=existing.name,
            job_count=jobs,
            added=existing.added,
            error=existing.error,
        )

    since = datetime.now(UTC) - timedelta(days=1)
    if await store.added_by_since(db, user_id, since) >= MAX_ADDS_PER_DAY:
        raise RateLimitedError(
            f"You can add up to {MAX_ADDS_PER_DAY} companies a day. Try again tomorrow."
        )
    if await store.added_total(db) >= MAX_ADDED_COMPANIES:
        raise ValidationFailedError(
            "We can't follow more companies right now. Pick from the list instead."
        )

    company = StoredCompany(
        slug=slug,
        name=detected.suggested_name,
        kind=detected.kind,
        config=detected.config,
        added=True,
    )
    try:
        audience = await load_audience(db)
        read = await asyncio.wait_for(
            collect([company], audience=audience, added_by=user_id, keep_failures=False),
            timeout=ADD_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise ValidationFailedError(
            "That careers site took too long to read. Try again in a minute."
        ) from exc
    saved = read.companies[slug]
    if saved.error:
        raise ValidationFailedError(
            "We found the careers site but could not read its jobs. Check the link opens "
            "the company's job list, then try again."
        )
    return CareerCompany(
        slug=slug,
        name=saved.name,
        job_count=len(read.jobs.get(slug, [])),
        added=True,
        error=None,
    )


def candidate_years_of(profile: ProfileRead) -> float:
    periods = [(item.start, item.end) for item in profile.experience if item.start]
    return scoring.years_of_experience(periods, datetime.now(UTC).date())


def _score(profile: ProfileRead, job: StoredJob, candidate_years: float) -> CareerJobRead | None:
    fit = fit_for(
        candidate_years,
        min_years=job.min_years,
        max_years=job.max_years,
        source=job.experience_source,
    )
    if fit is None:
        return None
    found = score_locally(profile, job.description, url=job.url)
    results = [
        SkillResult(
            name=item.name,
            required=item.required,
            verdict=item.verdict,
            evidence_label=item.evidence_label,
            evidence_text=item.evidence_text,
            reason=item.reason,
        )
        for item in found.judgements
    ]
    score: int | None = None
    cap: int | None = None
    boosts: list[ScoreBoost] = []
    if results:
        judged = [scoring.Judged(required=r.required, verdict=r.verdict) for r in results]
        raw = scoring.compute_score(judged)
        score, experience = scoring.check_experience(
            raw,
            required_min=job.min_years,
            required_max=job.max_years,
            source=job.experience_source,
            quote=job.experience_quote,
            candidate_years=candidate_years,
        )
        cap = scoring.score_cap(experience.status, experience.source)
        gains = scoring.score_gains(judged, current=score, cap=cap)
        boosts = sorted(
            (
                ScoreBoost(name=r.name, required=r.required, verdict=r.verdict, points=points)
                for r, points in zip(results, gains, strict=True)
                if points > 0
            ),
            key=lambda boost: (-boost.points, not boost.required, boost.name.lower()),
        )
    return CareerJobRead(
        id=job.id,
        company_slug=job.company_slug,
        company="",
        title=job.title,
        url=job.url,
        location=job.location,
        places=job.places,
        work_mode=work_mode_of(title=job.title, location=job.location, description=job.description),
        posted_on=job.posted_on,
        first_seen=job.first_seen,
        score=score,
        score_cap=cap,
        fit=fit.kind,
        fit_note=fit.note,
        skill_results=results,
        score_boosts=boosts,
    )


def _ranked(jobs: list[CareerJobRead]) -> list[CareerJobRead]:
    """A score from one or two recognised skills says little, so those jobs
    come after the ones with real evidence behind their score.
    """
    return sorted(
        jobs,
        key=lambda j: (
            j.score is None,
            len(j.skill_results) < WELL_EVIDENCED,
            -(j.score or 0),
            -(j.posted_on or j.first_seen).toordinal(),
        ),
    )


def _remember(key: tuple[uuid.UUID, int, int], jobs: list[CareerJobRead]) -> None:
    _cache[key] = jobs
    _previous[(key[0], key[1])] = jobs
    while len(_cache) > _CACHE_SIZE:
        _cache.popitem(last=False)


async def _begin(
    db: AsyncSession, profile: ProfileRead, user_id: uuid.UUID, collection: store.Collection
) -> None:
    """Starts scoring this collection if it is not already scored or underway."""
    key = (user_id, profile.version, collection.version)
    if key in _cache or key in _runs:
        if key in _cache:
            _cache.move_to_end(key)
        return
    # Claim the slot before the first await, so two opens of the page start one scoring.
    run = _Run(done=0, total=0)
    _runs[key] = run
    try:
        # Every company the collection knows, so one since dropped from the catalog keeps its name.
        names = {c.slug: c.name for c in collection.companies} | {
            c.slug: c.name for c in (await _companies(db)).values()
        }
    except Exception:
        _runs.pop(key, None)
        raise
    years = candidate_years_of(profile)
    jobs = list(collection.jobs)
    if not jobs:
        _remember(key, [])
        _runs.pop(key, None)
        return
    run.total = len(jobs)

    def work() -> list[CareerJobRead]:
        picked: list[CareerJobRead] = []
        for index, job in enumerate(jobs, start=1):
            scored = _score(profile, job, years)
            if scored is not None:
                picked.append(
                    scored.model_copy(
                        update={"company": names.get(job.company_slug, job.company_slug)}
                    )
                )
            # The page reads this between jobs, so the percent and the list can move.
            run.done = index
            if index == 1 or index % 20 == 0 or index == len(jobs):
                run.shown = _ranked(picked)
        return _ranked(picked)

    async def finish() -> None:
        try:
            # Scoring thousands of jobs is CPU work; keep the event loop free meanwhile.
            _remember(key, await asyncio.to_thread(work))
        except Exception:
            logger.exception("Scoring fresh jobs failed")
        finally:
            _runs.pop(key, None)

    run.task = asyncio.create_task(finish())


def _progress(key: tuple[uuid.UUID, int, int]) -> tuple[list[CareerJobRead], int, bool]:
    """The list to show, how much of the current scoring is done, and whether it is still going."""
    ready = _cache.get(key)
    if ready is not None:
        return ready, 100, False
    previous = _previous.get((key[0], key[1]), [])
    run = _runs.get(key)
    # Stay under 100 until the finished list replaces this one.
    percent = 0 if run is None or run.total == 0 else min(99, run.done * 100 // run.total)
    # A finished list for this profile stays up. Otherwise show whatever is already scored.
    shown = previous or (run.shown if run is not None and run.shown else [])
    return shown, percent, True


def _encode(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def _decode(cursor: str) -> int:
    try:
        return max(0, int(base64.urlsafe_b64decode(cursor.encode()).decode()))
    except (ValueError, binascii.Error) as exc:
        raise ValidationFailedError("Invalid cursor") from exc


async def list_jobs(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companies: list[str],
    places: list[str],
    work_modes: list[WorkMode],
    include_stretch: bool,
    cursor: str | None,
    limit: int,
) -> CareerJobPage:
    profile = await get_profile(db, user_id=user_id)
    collection = await store.current(db)
    await _begin(db, profile, user_id, collection)
    scored, percent, refreshing = _progress((user_id, profile.version, collection.version))
    since = date.today() - timedelta(days=collection.days or DAYS)

    chosen = set(companies)
    # A job the user applied to (or tracks already) is done; it is not shown again.
    tracked = await tracked_urls(db, user_id)
    in_companies = [
        job
        for job in scored
        if same_job(job.url) not in tracked
        and (not chosen or job.company_slug in chosen)
        and (include_stretch or job.fit != "stretch")
        and (job.posted_on or job.first_seen) >= since
    ]
    # Remote is a work mode, filtered on its own, so the city filter leaves it out.
    counts = Counter(place for job in in_companies for place in job.places if place != REMOTE)
    wanted = set(places)
    in_places = [job for job in in_companies if not wanted or wanted & set(job.places)]
    mode_counts = Counter(job.work_mode for job in in_places)
    modes = set(work_modes)
    matching = [job for job in in_places if not modes or job.work_mode in modes]

    start = _decode(cursor) if cursor else 0
    page = matching[start : start + limit]
    end = start + len(page)
    return CareerJobPage(
        items=page,
        next_cursor=_encode(end) if end < len(matching) else None,
        total=len(matching),
        places=[PlaceCount(name=n, count=c) for n, c in counts.most_common()],
        work_modes=[WorkModeCount(mode=m, count=c) for m, c in mode_counts.most_common()],
        collected_at=collection.collected_at,
        candidate_years=candidate_years_of(profile),
        scored_percent=percent,
        refreshing=refreshing,
    )
