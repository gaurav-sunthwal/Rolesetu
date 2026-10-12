import asyncio
import dataclasses
import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai import matching
from backend.ai.matching import EvidenceItem
from backend.core.config import get_settings
from backend.core.exceptions import (
    AppError,
    NotFoundError,
    RateLimitedError,
    ValidationFailedError,
)
from backend.core.pagination import Page, decode_cursor, encode_cursor
from backend.db.session import get_sessionmaker
from backend.modules.llm_keys.service import get_decrypted_user_llm_key
from backend.modules.matches import repository, scoring
from backend.modules.matches.fetching.job_page import is_job_list, read_job_page
from backend.modules.matches.fetching.safe_fetch import PASTE_INSTEAD, PageFetchError, fetch_page
from backend.modules.matches.local.engine import ENGINE_VERSION, LocalMatch, score_locally
from backend.modules.matches.local.experience import ExperienceAsk, read_experience
from backend.modules.matches.local.semantic import get_matcher
from backend.modules.matches.models import Job, Match
from backend.modules.matches.schemas import ExperienceCheck, MatchCreate, MatchRead, SkillResult
from backend.modules.profiles import service as profiles_service
from backend.modules.profiles.schemas import ProfileRead

logger = logging.getLogger(__name__)

# A model-backed check costs money; a local one costs nothing, so the limit
# there only guards against a runaway client.
MAX_CHECKS_PER_HOUR = {"llm": 20, "local": 600}
MAX_REQUIRED_SKILLS = 15
MAX_NICE_TO_HAVE_SKILLS = 10
# A pending check older than this was lost (the process restarted mid-run).
STALE_AFTER = timedelta(minutes=5)
# A listing read from a link is reused for this long before the page is fetched again.
PAGE_FRESH_FOR = timedelta(hours=24)
_EVIDENCE_TEXT_LIMIT = 280


def _content_hash(jd_text: str) -> str:
    normalised = re.sub(r"\s+", " ", jd_text).strip().lower()
    return hashlib.sha256(normalised.encode()).hexdigest()


def build_evidence(profile: ProfileRead) -> list[EvidenceItem]:
    """Flatten the profile into numbered evidence items the judge can point at."""
    items: list[tuple[str, str]] = []
    for job in profile.experience:
        period = f"{job.start} to {job.end or 'present'}. " if job.start else ""
        items.append((f"{job.title} at {job.company}", f"{period}{job.description}".strip()))
    for project in profile.projects:
        tech = f"Tech: {', '.join(project.tech)}. " if project.tech else ""
        items.append((f"Project: {project.name}", f"{tech}{project.description}".strip()))
    for school in profile.education:
        field = f" in {school.field}" if school.field else ""
        items.append((f"Education: {school.school}", f"{school.degree}{field}"))
    for skill in profile.skills:
        level = f" ({skill.level})" if skill.level else ""
        items.append(("Listed skill", f"{skill.name}{level}"))
    return [
        EvidenceItem(id=f"E{index}", label=label, text=text)
        for index, (label, text) in enumerate(items, start=1)
        if text
    ]


def _dedupe(names: list[str], *, exclude: set[str], limit: int) -> list[str]:
    seen = set(exclude)
    unique: list[str] = []
    for name in names:
        cleaned = name.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            unique.append(cleaned[:60])
    return unique[:limit]


def to_read(match: Match, now: datetime) -> MatchRead:
    status, error = match.status, match.error
    if status == "pending" and match.created_at < now - STALE_AFTER:
        status, error = "failed", "This check timed out. Please run it again."
    listing = _listing_of(match.job) or {}
    return MatchRead(
        id=match.id,
        status=status,  # type: ignore[arg-type]
        error=error,
        score=match.score,
        raw_score=match.raw_score,
        seniority_note=match.seniority_note,
        experience=(ExperienceCheck.model_validate(match.experience) if match.experience else None),
        score_cap=(
            scoring.score_cap(match.experience["status"], match.experience.get("source"))
            if match.experience
            else None
        ),
        role=match.job.role,
        company=match.job.company,
        url=match.job.url,
        location=listing.get("location"),
        employment_type=listing.get("employment_type"),
        salary=listing.get("salary"),
        skill_results=[SkillResult.model_validate(item) for item in match.skill_results],
        gaps=match.gaps,
        profile_version=match.profile_version,
        created_at=match.created_at,
    )


async def start_match(
    db: AsyncSession, *, user_id: uuid.UUID, payload: MatchCreate
) -> tuple[MatchRead, bool]:
    """Scores the job, or returns a result that can be reused.

    With the local engine the match comes back already completed. With the
    model engine it comes back pending and the second value is True, meaning
    the caller still has to run the scoring in the background.
    """
    engine = get_settings().match_engine
    now = datetime.now(UTC)
    profile = await profiles_service.get_profile(db, user_id=user_id)
    if not build_evidence(profile):
        raise ValidationFailedError(
            "Add your skills, experience or projects to your profile first, "
            "so there is something to score the job against."
        )

    jd_text, role, company = payload.jd_text, payload.role, payload.company
    listing: dict[str, str | None] | None = None
    if not jd_text:
        assert payload.url is not None  # the request schema guarantees one of the two
        jd_text, role, company, listing = await _read_link(
            db, user_id, payload.url, role, company, now
        )

    content_hash = _content_hash(jd_text)
    job = await repository.find_job(db, user_id, content_hash)
    if job is None:
        job = Job(
            user_id=user_id,
            url=payload.url or None,
            role=role or None,
            company=company or None,
            jd_text=jd_text,
            content_hash=content_hash,
            job_json={"listing": listing} if listing else None,
        )
        db.add(job)
        await db.flush()
    else:
        # A title or company supplied now (by the user, or read off the page by the
        # extension) replaces one stored earlier, including one we had to infer.
        # Done before the cache check, so a reused result shows the right title too.
        job.url = payload.url or job.url
        job.role = role or job.role
        job.company = company or job.company
        reusable = await repository.find_reusable(
            db,
            user_id,
            job.id,
            profile.version,
            ENGINE_VERSION if engine == "local" else matching.PROMPT_VERSIONS,
            fresh_after=now - STALE_AFTER,
        )
        if reusable is not None:
            return to_read(reusable, now), False

    limit = MAX_CHECKS_PER_HOUR[engine]
    if await repository.count_since(db, user_id, now - timedelta(hours=1)) >= limit:
        raise RateLimitedError(
            f"You have checked {limit} jobs in the last hour. "
            "Please wait a little before checking more."
        )

    # The job is attached in memory, so the response is built from what we
    # already hold instead of reading the rows back from the database.
    match = Match(user_id=user_id, job=job, profile_version=profile.version)
    if engine == "local":
        # Off the event loop: the embedding pass is CPU work.
        found = await asyncio.to_thread(score_locally, profile, job.jd_text, get_matcher(), job.url)
        _store_local(job, match, profile, found)
    db.add(match)
    await db.flush()
    return to_read(match, now), engine == "llm"


async def get_match(db: AsyncSession, *, user_id: uuid.UUID, match_id: uuid.UUID) -> MatchRead:
    match = await repository.get(db, user_id, match_id)
    if match is None:
        raise NotFoundError("Match not found")
    return to_read(match, datetime.now(UTC))


async def list_matches(
    db: AsyncSession, *, user_id: uuid.UUID, cursor: str | None, limit: int
) -> Page[MatchRead]:
    after = decode_cursor(cursor) if cursor else None
    rows = await repository.list_page(db, user_id, after=after, limit=limit + 1)
    has_more = len(rows) > limit
    rows = rows[:limit]
    now = datetime.now(UTC)
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    return Page(items=[to_read(row, now) for row in rows], next_cursor=next_cursor)


async def _read_link(
    db: AsyncSession,
    user_id: uuid.UUID,
    url: str,
    role: str | None,
    company: str | None,
    now: datetime,
) -> tuple[str, str | None, str | None, dict[str, str | None] | None]:
    """Gets a job's description from its link: (text, role, company, listing details)."""
    known = await repository.find_job_by_url(db, user_id, url, now - PAGE_FRESH_FOR)
    # Only a job that was itself read from the page is reused; one the user
    # pasted by hand has no listing details, so the page is fetched for those.
    if known is not None and (listing := _listing_of(known)) is not None:
        return known.jd_text, role or known.role, company or known.company, listing

    _, markup = await fetch_page(url)
    page = read_job_page(markup)
    if page is None:
        if is_job_list(markup):
            raise PageFetchError(
                "That link is a list of jobs, not one job. Open the job you want and use its link."
            )
        raise PageFetchError(f"We could not find a job description on that page. {PASTE_INSTEAD}")
    listing = {
        "location": page.location,
        "employment_type": page.employment_type,
        "salary": page.salary,
        "posted_on": page.posted_on,
        "source": page.source,
    }
    return page.as_text()[:20000], role or page.title, company or page.company, listing


def _listing_of(job: Job) -> dict[str, str | None] | None:
    listing = (job.job_json or {}).get("listing")
    return listing if isinstance(listing, dict) else None


def _finish(
    job: Job,
    match: Match,
    profile: ProfileRead,
    results: list[SkillResult],
    *,
    asked: ExperienceAsk,
    engine_version: str,
) -> None:
    """Turns verdicts into a score. The same maths whichever engine judged them."""
    raw_score = scoring.compute_score(
        [scoring.Judged(required=r.required, verdict=r.verdict) for r in results]
    )
    candidate_years = scoring.years_of_experience(
        [(item.start, item.end) for item in profile.experience if item.start],
        datetime.now(UTC).date(),
    )
    score, experience = scoring.check_experience(
        raw_score,
        required_min=asked.min_years,
        required_max=asked.max_years,
        source=asked.source,
        quote=asked.quote,
        candidate_years=candidate_years,
        includes_internships=any(
            re.search(r"\bintern", item.title, re.IGNORECASE) for item in profile.experience
        ),
    )
    match.skill_results = [r.model_dump() for r in results]
    match.gaps = [r.name for r in results if r.verdict == "missing"]
    match.raw_score = raw_score
    match.score = score
    # The warning line is kept for older clients; `experience` is always filled.
    match.seniority_note = (
        experience.summary if experience.status in ("short", "well_short") else None
    )
    match.experience = dataclasses.asdict(experience)
    match.prompt_versions = engine_version
    match.status = "completed"


def _store_local(job: Job, match: Match, profile: ProfileRead, found: LocalMatch) -> None:
    """Saves a locally scored result. No network call was made to produce it."""
    if not found.judgements:
        raise ValidationFailedError(
            "We could not find any skills we recognise in that text. "
            "Paste the full job description, including the requirements section."
        )
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
    job.role = job.role or found.job.role
    job.company = job.company or found.job.company
    job.job_json = {
        "listing": _listing_of(job),
        "role": found.job.role,
        "company": found.job.company,
        "min_years_experience": found.job.min_years,
        "required_skills": [item.name for item in found.job.requirements if item.required],
        "nice_to_have_skills": [item.name for item in found.job.requirements if not item.required],
    }
    # The title the page gave counts too: "Senior ..." says something even when
    # the description gives no number of years.
    asked = read_experience(job.jd_text, job.role)
    _finish(job, match, profile, results, asked=asked, engine_version=ENGINE_VERSION)


async def _score(db: AsyncSession, match: Match) -> None:
    job = match.job
    profile = await profiles_service.get_profile(db, user_id=match.user_id)
    evidence = build_evidence(profile)
    user_api_key = await get_decrypted_user_llm_key(db, user_id=match.user_id)

    extracted = await matching.extract_job(job.jd_text, user_api_key=user_api_key)
    required = _dedupe(extracted.required_skills, exclude=set(), limit=MAX_REQUIRED_SKILLS)
    nice = _dedupe(
        extracted.nice_to_have_skills,
        exclude={name.lower() for name in required},
        limit=MAX_NICE_TO_HAVE_SKILLS,
    )
    if not required and not nice:
        raise ValidationFailedError(
            "We could not find any skills in that text. "
            "Paste the full job description, including the requirements section."
        )

    skills = [(name, True) for name in required] + [(name, False) for name in nice]
    judgements = await matching.judge_skills(
        [name for name, _ in skills], evidence, user_api_key=user_api_key
    )
    evidence_by_id = {item.id: item for item in evidence}

    results: list[SkillResult] = []
    for index, (name, is_required) in enumerate(skills):
        judgement = judgements.get(index)
        verdict = judgement.verdict if judgement else "missing"
        cited = (
            evidence_by_id.get((judgement.evidence_id or "").strip().upper()) if judgement else None
        )
        # Grounding: a positive verdict has to point at a real evidence item.
        if verdict != "missing" and cited is None:
            verdict = "missing"
        if verdict == "missing":
            cited = None
        results.append(
            SkillResult(
                name=name,
                required=is_required,
                verdict=verdict,
                evidence_label=cited.label if cited else None,
                evidence_text=cited.text[:_EVIDENCE_TEXT_LIMIT] if cited else None,
                reason=(judgement.reason.strip()[:240] or None) if judgement else None,
            )
        )

    job.role = job.role or (extracted.role or None)
    job.company = job.company or (extracted.company or None)
    job.job_json = {"listing": _listing_of(job), **extracted.model_dump()}
    _finish(
        job,
        match,
        profile,
        results,
        asked=(
            ExperienceAsk(min_years=extracted.min_years_experience, source="stated")
            if extracted.min_years_experience
            else read_experience(job.jd_text, job.role)
        ),
        engine_version=matching.PROMPT_VERSIONS,
    )


async def run_match(match_id: uuid.UUID) -> None:
    """Runs after the response has been sent, in its own database session."""
    async with get_sessionmaker()() as db:
        match = await repository.get_by_id(db, match_id)
        if match is None or match.status != "pending":
            return
        try:
            await _score(db, match)
        except AppError as exc:
            await db.rollback()
            await _mark_failed(db, match_id, exc.detail)
            return
        except Exception:
            logger.exception("Match %s failed", match_id)
            await db.rollback()
            await _mark_failed(db, match_id, "Scoring failed unexpectedly. Please try again.")
            return
        await db.commit()


async def _mark_failed(db: AsyncSession, match_id: uuid.UUID, message: str) -> None:
    match = await repository.get_by_id(db, match_id)
    if match is not None:
        match.status = "failed"
        match.error = message
        await db.commit()
