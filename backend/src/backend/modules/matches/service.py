import asyncio
import dataclasses
import functools
import hashlib
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
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
from backend.modules.ai_calls import service as ai_calls
from backend.modules.domain_catalogs import repository as domain_catalogs_repository
from backend.modules.domain_catalogs import service as domain_catalogs_service
from backend.modules.errors import service as errors_service
from backend.modules.llm_keys.service import get_decrypted_user_llm_key
from backend.modules.matches import repository, scoring
from backend.modules.matches.fetching.job_page import JobPage
from backend.modules.matches.fetching.reader import load_job_page
from backend.modules.matches.job_key import job_key
from backend.modules.matches.local import fields
from backend.modules.matches.local.catalog import in_dictionary, lookup
from backend.modules.matches.local.domain_catalogs import field_keys_for_profile
from backend.modules.matches.local.engine import ENGINE_VERSION, LocalMatch, score_locally
from backend.modules.matches.local.experience import ExperienceAsk, read_experience
from backend.modules.matches.local.jd import Requirement
from backend.modules.matches.local.judge import ProfileIndex
from backend.modules.matches.local.must_haves import MustHave, find_must_haves
from backend.modules.matches.local.semantic import Matcher, get_matcher
from backend.modules.matches.models import Job, Match
from backend.modules.matches.schemas import (
    ExperienceCheck,
    FieldFitCheck,
    MatchCreate,
    MatchRead,
    ScoreLimit,
    SkillResult,
)
from backend.modules.previews import service as previews_service
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
# A job recognised by its id (see `job_key`) reuses its result for this long, even
# when the page text came out differently this time.
JOB_KEY_FRESH_FOR = timedelta(days=7)
# How many recent checks to look through for skills already judged.
REMEMBERED_CHECKS = 30
# Each read through Context.dev spends a paid credit, so one person cannot use up
# the month's allowance in an afternoon.
MAX_RENDERED_READS_PER_DAY = 25
_EVIDENCE_TEXT_LIMIT = 280
# The model path's results also depend on the scoring rules applied after it,
# so both are named: a change to either means old results are not reused.
MODEL_VERSION = f"{matching.PROMPT_VERSIONS}+score.v2"


def _current_versions() -> tuple[str, ...]:
    """Results that can be reused. The local engine scores every job itself, so
    an older model reading is not reused there: the job is scored again, free.
    """
    return (MODEL_VERSION,) if get_settings().match_engine == "llm" else (ENGINE_VERSION,)


# Words nearly every job posting uses, and other text does not.
_ENTRY_LEVEL = re.compile(
    r"\bintern(?:ship)?\b|\bfreshers?\b|prior experience is not|experience is not mandatory|"
    r"no prior experience|experience is not required",
    re.IGNORECASE,
)
_JOB_WORDS = re.compile(
    r"responsibilit|requirement|qualification|experience|skills?\b|candidate|"
    r"\brole\b|apply|hiring|position|duties|job description",
    re.IGNORECASE,
)
# Names of results that are qualifications rather than skills.
_QUALIFICATION = re.compile(
    r"licen[cs]e|degree|certif|clearance|bachelor|master|\bcpa\b|\bpmp\b|\bosha\b",
    re.IGNORECASE,
)
_QUALIFICATION_FILLER = frozenset(
    {"degree", "in", "license", "licence", "certification", "certified", "and", "or", "the", "a"}
)


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
    assessment = (match.experience or {}).get("assessment") or {}
    caps = [scoring.Cap(**cap) for cap in assessment.get("caps", [])]
    if not assessment and match.experience:
        # Scored before the assessment was recorded: only experience limited it.
        old_cap = scoring.score_cap(match.experience["status"], match.experience.get("source"))
        caps = [] if old_cap is None else [scoring.Cap("experience", old_cap, "")]
    fit = assessment.get("field_fit")
    return MatchRead(
        id=match.id,
        status=status,  # type: ignore[arg-type]
        error=error,
        score=match.score,
        raw_score=match.raw_score,
        seniority_note=match.seniority_note,
        experience=(ExperienceCheck.model_validate(match.experience) if match.experience else None),
        score_cap=min((cap.limit for cap in caps), default=None),
        summary=(_summary(match, caps) if status == "completed" else None),
        screened=bool(assessment.get("screened")),
        field_fit=FieldFitCheck.model_validate(fit) if fit else None,
        limits=[
            ScoreLimit(kind=cap.kind, limit=cap.limit, reason=cap.reason)
            for cap in caps
            if cap.reason
            and (
                (match.raw_score is not None and cap.limit < match.raw_score)
                or (cap.kind == "field" and assessment.get("screened"))
            )
        ],
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


def _summary(match: Match, caps: list[scoring.Cap]) -> str | None:
    """Why the score is what it is, in one sentence.

    The limit that held the score lowest explains it best ("This is a mechanical
    engineering role, but your work has been in software engineering"). With
    none, it is the skills: how many required ones the profile shows, and the
    first few it does not.
    """
    if match.score is None:
        return None
    # A job in another line of work is explained by that, whatever its skills
    # add up to: it is the first thing an employer screens on.
    field = next((cap for cap in caps if cap.kind == "field"), None)
    if field is not None and field.reason:
        return field.reason
    background = ((match.experience or {}).get("assessment") or {}).get("background")
    if background and match.raw_score is not None and (match.score or 0) > match.raw_score:
        return background
    biting = [cap for cap in caps if cap.reason and cap.limit < (match.raw_score or 0)]
    if biting:
        return min(biting, key=lambda cap: cap.limit).reason
    required = [item for item in match.skill_results if item.get("required")]
    if not required:
        return "This posting lists no hard requirements, so the score rests on its nice-to-haves."
    shown = sum(1 for item in required if item.get("verdict") != "missing")
    missing = [str(item["name"]) for item in required if item.get("verdict") == "missing"]
    sentence = f"Your profile shows {shown} of the {len(required)} skills this job requires."
    if missing:
        sentence += f" Missing: {', '.join(missing[:3])}{'…' if len(missing) > 3 else ''}."
    return sentence


@dataclass(frozen=True)
class Started:
    """What a job check produced. `needs_model`: the caller still has to run the
    model in the background. `save`: the caller saves it after answering (see
    `start_match`).
    """

    match: MatchRead
    needs_model: bool = False
    save: Callable[[], Awaitable[None]] | None = None


async def start_match(
    db: AsyncSession, *, user_id: uuid.UUID, payload: MatchCreate, paid_reads: bool = True
) -> Started:
    """Scores the job, or returns a result that can be reused.

    Every query is a round trip to the database, so the order is chosen to make
    as few as possible before the person sees an answer:

    - a job seen before is found in one query, by its id or its text;
    - a new job scored here is answered first and saved just after, by
      `Started.save`, while the person is already reading the result;
    - with the model engine, the job is saved first, because the background
      run that scores it loads it from the database.

    `paid_reads`: whether a link may be read through the paid page reader. The
    extension has the page in front of it and sends its text, so it never needs one.
    """
    engine = get_settings().match_engine
    now = datetime.now(UTC)
    key = job_key(payload.url)
    jd_text, role, company = payload.jd_text, payload.role, payload.company

    async def saved(content_hash: str | None) -> Match | None:
        return await repository.find_saved_result(
            db,
            user_id,
            job_key=key,
            content_hash=content_hash,
            engine_versions=_current_versions(),
            key_scored_after=now - JOB_KEY_FRESH_FOR,
            fresh_after=now - STALE_AFTER,
        )

    # The same job seen again (a repeat visit, a reload): reuse its result
    # before reading the page, whatever the page shows now.
    if (seen := await saved(_content_hash(jd_text) if jd_text else None)) is not None:
        return Started(to_read(seen, now))

    listing: dict[str, str | None] | None = None
    if not jd_text:
        assert payload.url is not None  # the request schema guarantees one of the two
        jd_text, role, company, listing = await _read_link(
            db, user_id, payload.url, role, company, now, paid_reads=paid_reads
        )
        if (seen := await saved(_content_hash(jd_text))) is not None:
            return Started(to_read(seen, now))

    profile = await profiles_service.get_profile(db, user_id=user_id)
    if not build_evidence(profile):
        raise ValidationFailedError(
            "Add your skills, experience or projects to your profile first, "
            "so there is something to score the job against."
        )

    limit = MAX_CHECKS_PER_HOUR[engine]
    if await repository.count_since(db, user_id, now - timedelta(hours=1)) >= limit:
        raise RateLimitedError(
            f"You have checked {limit} jobs in the last hour. "
            "Please wait a little before checking more."
        )

    # Built in memory, with their ids and times set here, so the answer can be
    # made before anything is written.
    job = Job(
        id=uuid.uuid4(),
        user_id=user_id,
        url=payload.url or None,
        role=role or None,
        company=company or None,
        jd_text=jd_text,
        content_hash=_content_hash(jd_text),
        job_json=({"listing": listing} if listing else {}) | ({"job_key": key} if key else {})
        or None,
        created_at=now,
    )
    match = Match(
        id=uuid.uuid4(),
        user_id=user_id,
        job=job,
        profile_version=profile.version,
        status="pending",
        created_at=now,
    )
    fit = _field_fit(profile, role or payload.role, jd_text)
    if fit.status == "different":
        # Title and profile already disagree. Say so. Do not build a catalog
        # and do not ask a model what the job wants.
        _record_different_field(job, match, fit)
        answer = to_read(match, now)
        return Started(answer, save=functools.partial(_save_in_background, job, match))

    if engine == "local":
        # A catalog is built only for the field this person is in.
        catalog_keys = field_keys_for_profile(profile)
        for field_key in catalog_keys:
            await domain_catalogs_service.ensure_catalog(db, field_key)
        job_title = role or payload.role
        job_field = fields.field_of(job_title) if job_title else None
        if job_field is not None and job_field.key not in catalog_keys:
            stored = await domain_catalogs_repository.get(db, job_field.key)
            if stored is not None:
                catalog_keys.add(job_field.key)
        catalog_append = await domain_catalogs_service.catalog_append_for_fields(db, catalog_keys)
        await asyncio.to_thread(
            score_without_model, job, match, profile, get_matcher(), catalog_append
        )
        answer = to_read(match, now)
        # A partial of the async function itself, not a lambda: the task runner
        # awaits only what it can see is async, and would otherwise call a
        # lambda in a thread and drop the save it returns without running it.
        return Started(answer, save=functools.partial(_save_in_background, job, match))

    await _save(db, job, match)
    return Started(to_read(match, now), needs_model=True)


async def _save(db: AsyncSession, job: Job, match: Match) -> None:
    """Writes a check and its job. A job this user checked before (the same text)
    keeps its row, brought up to date with what was learnt now.
    """
    existing = await repository.find_job(db, job.user_id, job.content_hash)
    if existing is None:
        db.add(job)
    else:
        existing.url = job.url or existing.url
        existing.role = job.role or existing.role
        existing.company = job.company or existing.company
        # A new reading of the job (it was scored just now) replaces the stored
        # one; otherwise the stored one stays, with any model reading in it.
        fresh = job.job_json or {}
        merged = dict(fresh if "required_skills" in fresh else (existing.job_json or {}))
        if (listing := _listing_of(job) or _listing_of(existing)) is not None:
            merged["listing"] = listing
        merged.update(_identity(job) or _identity(existing))
        existing.job_json = merged
        match.job = existing
    db.add(match)
    await db.flush()


async def _save_in_background(job: Job, match: Match) -> None:
    """Saves a check already shown to the person, in its own session. A failure
    here loses only the stored copy (the next check of the job scores it again),
    so it is recorded, not raised.
    """
    try:
        async with get_sessionmaker()() as db:
            await _save(db, job, match)
            await db.commit()
    except Exception as exc:
        logger.exception("Could not save job check %s", match.id)
        await errors_service.record(source="job-check", exc=exc, message=str(exc))


async def get_match(db: AsyncSession, *, user_id: uuid.UUID, match_id: uuid.UUID) -> MatchRead:
    match = await repository.get_when_saved(db, user_id, match_id)
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
    *,
    paid_reads: bool = True,
) -> tuple[str, str | None, str | None, dict[str, str | None] | None]:
    """Gets a job's description from its link: (text, role, company, listing details)."""
    known = await repository.find_job_by_url(db, user_id, url, now - PAGE_FRESH_FOR)
    # Only a job that was itself read from the page is reused; one the user
    # pasted by hand has no listing details, so the page is fetched for those.
    if known is not None and (listing := _listing_of(known)) is not None:
        return known.jd_text, role or known.role, company or known.company, listing

    page, reader = await _load_job_page(db, user_id, url, now, paid_reads=paid_reads)
    listing = {
        "location": page.location,
        "employment_type": page.employment_type,
        "salary": page.salary,
        "posted_on": page.posted_on,
        "source": page.source,
        "reader": reader,
    }
    return page.as_text()[:20000], role or page.title, company or page.company, listing


async def _load_job_page(
    db: AsyncSession, user_id: uuid.UUID, url: str, now: datetime, *, paid_reads: bool = True
) -> tuple[JobPage, str]:
    """Reads the job at a link: (job, how it was fetched)."""
    # Someone may have just previewed this job on the landing page before
    # signing in; that read is reused instead of fetching the page again.
    previewed = await previews_service.fresh_page(db, url, now)
    if previewed is not None:
        return previewed, "preview"

    async def within_allowance() -> bool:
        if not paid_reads:
            return False
        used = await repository.count_rendered_reads(db, user_id, now - timedelta(days=1))
        if used >= MAX_RENDERED_READS_PER_DAY:
            logger.info("rendered fetch skipped: daily allowance used user=%s", user_id)
        return used < MAX_RENDERED_READS_PER_DAY

    return await load_job_page(url, within_allowance)


def _identity(job: Job) -> dict[str, str]:
    """The job's id from its link, kept whenever the job's details are rewritten."""
    key = (job.job_json or {}).get("job_key")
    return {"job_key": key} if isinstance(key, str) else {}


def _listing_of(job: Job) -> dict[str, str | None] | None:
    listing = (job.job_json or {}).get("listing")
    return listing if isinstance(listing, dict) else None


def _role_line(jd_text: str) -> str | None:
    """The first short line that names a field, when the page sent no job title."""
    for line in jd_text.splitlines():
        line = line.strip()
        if 3 <= len(line) <= 80 and fields.field_of(line) is not None:
            return line
    return None


def _field_fit(profile: ProfileRead, role: str | None, jd_text: str) -> fields.FieldFit:
    title = role or _role_line(jd_text)
    return fields.compare(fields.field_of(title), _person_fields(profile))


def _record_different_field(job: Job, match: Match, fit: fields.FieldFit) -> None:
    """The title already says this is another field. No catalog and no model."""
    if not job.role:
        job.role = _role_line(job.jd_text)
    cap = scoring.Cap("field", scoring.FIELD_CAP, fit.summary)
    match.skill_results = []
    match.gaps = []
    match.raw_score = 0
    match.score = scoring.FIELD_CAP
    match.seniority_note = None
    match.experience = {
        "status": "not_stated",
        "required_min": None,
        "required_max": None,
        "candidate_years": 0.0,
        "source": None,
        "quote": None,
        "summary": "Experience was not checked, because this is not your field.",
        "total_years": None,
        "assessment": {
            "field_fit": {
                "status": fit.status,
                "job_field": fields.label(fit.job_field) if fit.job_field else None,
                "candidate_fields": [fields.label(key) for key in fit.candidate_fields],
                "summary": fit.summary,
            },
            "caps": [dataclasses.asdict(cap)],
            "screened": True,
            "background": None,
        },
    }
    match.prompt_versions = ENGINE_VERSION
    match.status = "completed"


def _person_fields(profile: ProfileRead) -> list[str]:
    found = fields.fields_of_person(
        [(item.title, item.start, item.end) for item in profile.experience],
        profile.headline,
        [f"{item.field or ''} {item.degree}" for item in profile.education],
    )
    # The field they confirmed is where they are going, even when past titles
    # are in another line of work.
    if profile.field_key and profile.field_key not in found:
        found.append(profile.field_key)
    return found


def _same_qualification(name: str, must: MustHave) -> bool:
    """Whether a judged skill is the same qualification a must-have names."""
    if not _QUALIFICATION.search(name):
        return False

    def words(text: str) -> set[str]:
        tokens = re.findall(r"[a-z]+", text.lower())
        return {token for token in tokens if token not in _QUALIFICATION_FILLER}

    return bool(words(name) & words(must.name))


def _with_must_haves(results: list[SkillResult], musts: list[MustHave]) -> list[SkillResult]:
    """Adds each must-have as a required line, replacing the same qualification
    if the skills list already had it, so it is judged once, by these rules.
    """
    kept = [r for r in results if not any(_same_qualification(r.name, m) for m in musts)]
    added = [
        SkillResult(
            name=must.name,
            required=True,
            verdict="strong" if must.held else "missing",
            evidence_label=must.evidence,
            evidence_text=None,
            reason=(
                "Required by the posting, and your profile shows it."
                if must.held
                else f"Required by the posting (“{must.quote}”), and your profile does not show it."
            )[:240],
        )
        for must in musts
    ]
    return added + kept


def _title_weight(name: str, role: str | None) -> float:
    """A skill the job title names is the core of the job."""
    if not role:
        return 1.0
    for option in name.split(" or "):
        if option and re.search(rf"(?<![A-Za-z0-9]){re.escape(option)}(?![A-Za-z0-9])", role, re.I):
            return scoring.TITLE_WEIGHT
    return 1.0


def _finish(
    job: Job,
    match: Match,
    profile: ProfileRead,
    results: list[SkillResult],
    *,
    asked: ExperienceAsk,
    engine_version: str,
    screened: bool = False,
    checked: int | None = None,
) -> None:
    """Turns verdicts into a score. The same maths whichever engine judged them.

    The score from skills is then limited by anything that rules the job out
    whatever the skills say: a different line of work, a missing licence or
    degree, too little experience in the job's field, or too little in the
    posting to check. Each limit carries the sentence that explains it.

    `checked`: how many requirements were read from the posting itself (see
    `ParsedJob.understood`); by default, every result.
    """
    today = datetime.now(UTC).date()
    checked = len(results) if checked is None else checked
    musts = find_must_haves(job.jd_text, profile)
    results = _with_must_haves(results, musts)
    raw_score = scoring.compute_score(
        [
            scoring.Judged(
                required=r.required, verdict=r.verdict, weight=_title_weight(r.name, job.role)
            )
            for r in results
        ]
    )

    job_field = fields.field_of(job.role)
    fit = fields.compare(job_field, _person_fields(profile))

    # Years count only in the job's own field and the ones close to it. A role
    # whose title names no field is given the benefit of the doubt.
    def counts(title: str) -> bool:
        if job_field is None:
            return True
        own = fields.field_of(title)
        return own is None or own.key == job_field.key or fields.related(own.key, job_field.key)

    total_years = scoring.years_of_experience(
        [(item.start, item.end) for item in profile.experience if item.start], today
    )
    field_years = scoring.years_of_experience(
        [
            (item.start, item.end)
            for item in profile.experience
            if item.start and counts(item.title)
        ],
        today,
    )
    _, experience = scoring.check_experience(
        raw_score,
        required_min=asked.min_years,
        required_max=asked.max_years,
        source=asked.source,
        quote=asked.quote,
        candidate_years=field_years,
        includes_internships=any(
            re.search(r"\bintern", item.title, re.IGNORECASE) for item in profile.experience
        ),
        field_label=job_field.label if job_field else None,
        total_years=total_years,
    )

    caps: list[scoring.Cap] = []
    experience_cap = scoring.score_cap(experience.status, experience.source)
    if experience_cap is not None:
        caps.append(scoring.Cap("experience", experience_cap, experience.summary))
    if fit.status == "different":
        caps.append(scoring.Cap("field", scoring.FIELD_CAP, fit.summary))
    missing = [must.name for must in musts if not must.held]
    if missing:
        caps.append(
            scoring.Cap(
                "must_have",
                scoring.MUST_HAVE_CAP,
                f"The posting requires {' and '.join(missing)}, which your profile does not show. "
                "Employers usually screen these out first.",
            )
        )
    # A screened job was never read in full, so "too few skills" is expected there
    # and the field limit already explains the score.
    if checked < scoring.MIN_CHECKED and not screened:
        caps.append(
            scoring.Cap(
                "thin",
                scoring.THIN_CAP,
                f"This posting names only {checked} skill{'s' if checked != 1 else ''} we could "
                "check, so a high score would not mean much. Read the full listing.",
            )
        )
    score, _ = scoring.apply_caps(raw_score, caps)
    entry_level = bool(_ENTRY_LEVEL.search(f"{job.role or ''}\n{job.jd_text[:2000]}"))
    floor = scoring.entry_aim_floor(same_field=fit.status == "same", entry_level=entry_level)
    background = None
    if floor is not None and score < floor and not any(cap.kind == "must_have" for cap in caps):
        score = floor
        label = job_field.label if job_field else "this"
        background = (
            f"This is an entry-level {label} role, and your profile is aimed at that work. "
            "You have not shown the specific skills yet, so treat it as a stretch, not a blank."
        )

    match.skill_results = [r.model_dump() for r in results]
    match.gaps = [r.name for r in results if r.verdict == "missing"]
    match.raw_score = raw_score
    match.score = score
    # The warning line is kept for older clients; `experience` is always filled.
    match.seniority_note = (
        experience.summary if experience.status in ("short", "well_short") else None
    )
    match.experience = {
        **dataclasses.asdict(experience),
        # Kept beside the experience check so no new column is needed (ADR 0009).
        "assessment": {
            "field_fit": {
                "status": fit.status,
                "job_field": fields.label(fit.job_field) if fit.job_field else None,
                "candidate_fields": [fields.label(key) for key in fit.candidate_fields],
                "summary": fit.summary,
            },
            "caps": [dataclasses.asdict(cap) for cap in caps],
            "screened": screened,
            "background": background,
        },
    }
    match.prompt_versions = engine_version
    match.status = "completed"


def score_without_model(
    job: Job,
    match: Match,
    profile: ProfileRead,
    matcher: Matcher | None,
    catalog_append: str = "",
) -> None:
    """Scores the job on this machine alone: no model call, no network, no cost.

    Every job is answered here. The dictionary covers software, data and the
    common skills of other fields; what it does not know is read from how the
    posting asks for it ("knowledge of X"). A posting with too few of either
    is still scored, held down by the "too little to check" limit. Text that
    is not a job posting at all is turned away. Pure apart from the objects it
    fills in.
    """
    fit = _field_fit(profile, job.role, job.jd_text)
    if fit.status == "different":
        _record_different_field(job, match, fit)
        return

    found = score_locally(profile, job.jd_text, matcher, job.url, catalog_append)
    if (
        not found.job.requirements
        and fields.field_of(job.role or found.job.role) is None
        and not _JOB_WORDS.search(job.jd_text)
    ):
        raise ValidationFailedError(
            "That does not look like a job description. "
            "Paste the full job posting, including the requirements section."
        )
    _store_local(job, match, profile, found)


def _store_local(job: Job, match: Match, profile: ProfileRead, found: LocalMatch) -> None:
    """Saves a locally scored result. No network call was made to produce it."""
    judgements = found.judgements
    if not judgements:
        raise ValidationFailedError(
            "We could not find any skills in this posting to compare with your profile. "
            "Make sure the full job description, including its requirements, is showing."
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
        for item in judgements
    ]
    job.role = job.role or found.job.role
    job.company = job.company or found.job.company
    job.job_json = {
        **_identity(job),
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
    _finish(
        job,
        match,
        profile,
        results,
        asked=asked,
        engine_version=ENGINE_VERSION,
        checked=found.job.understood,
    )


def _saved_extraction(job_json: dict[str, object] | None) -> matching.ExtractedJob | None:
    """A model reading of a job, if one was saved under the current extract prompt."""
    if not job_json or job_json.get("extract_version") != matching.EXTRACT_PROMPT_VERSION:
        return None
    return matching.ExtractedJob.model_validate(job_json)


async def _score(db: AsyncSession, match: Match) -> None:
    profile = await profiles_service.get_profile(db, user_id=match.user_id)
    user_api_key = await get_decrypted_user_llm_key(db, user_id=match.user_id)
    # Reading the job does not depend on who reads it, so it is done once per
    # posting: this user's earlier check of it (their profile has changed since),
    # or anyone's. Only judging the skills against this profile is new work.
    known = _saved_extraction(match.job.job_json) or _saved_extraction(
        await repository.find_extraction(
            db,
            match.job.content_hash,
            _identity(match.job).get("job_key"),
            matching.EXTRACT_PROMPT_VERSION,
        )
    )
    # Skills already judged against this same profile, on other jobs.
    remembered: dict[str, SkillResult] = {}
    for results in await repository.judged_skills(
        db, match.user_id, profile.version, MODEL_VERSION, REMEMBERED_CHECKS
    ):
        for item in results:
            remembered.setdefault(str(item["name"]).lower(), SkillResult.model_validate(item))
    await score_with_model(
        match.job,
        match,
        profile,
        user_api_key=user_api_key,
        known=known,
        remembered=remembered,
    )


async def score_with_model(
    job: Job,
    match: Match,
    profile: ProfileRead,
    *,
    user_api_key: str | None,
    known: matching.ExtractedJob | None = None,
    remembered: dict[str, SkillResult] | None = None,
) -> None:
    """The model reads the job (unless `known` already holds that reading) and
    judges the skills nothing else can; the score is worked out here, by the
    same rules as the local engine. No database access.

    Each skill is judged by the cheapest thing that can: the dictionary for a
    skill it knows (free, and the same answer every time), then a verdict
    already given for this profile on another job (`remembered`), and only then
    the model. A job whose skills are all known costs no judging call at all.
    """
    fit = _field_fit(profile, job.role, job.jd_text)
    if fit.status == "different":
        _record_different_field(job, match, fit)
        return

    evidence = build_evidence(profile)

    extracted = known or await matching.extract_job(job.jd_text, user_api_key=user_api_key)
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
    settled: dict[int, SkillResult] = {}
    on_profile = ProfileIndex(profile, get_matcher())
    for position, (name, is_required) in enumerate(skills):
        options = [lookup(option) for option in name.split(" or ")]
        if options and all(skill is not None and in_dictionary(skill) for skill in options):
            found = on_profile.judge(
                Requirement(tuple(skill for skill in options if skill), is_required)
            )
            settled[position] = SkillResult(
                name=name,
                required=is_required,
                verdict=found.verdict,
                evidence_label=found.evidence_label,
                evidence_text=found.evidence_text,
                reason=found.reason,
            )
        elif (earlier := (remembered or {}).get(name.lower())) is not None:
            settled[position] = earlier.model_copy(update={"name": name, "required": is_required})

    to_ask = [position for position in range(len(skills)) if position not in settled]
    asked = (
        await matching.judge_skills(
            [skills[position][0] for position in to_ask], evidence, user_api_key=user_api_key
        )
        if to_ask
        else {}
    )
    judgements = {to_ask[number]: judgement for number, judgement in asked.items()}
    evidence_by_id = {item.id: item for item in evidence}

    results: list[SkillResult] = []
    for position, (name, is_required) in enumerate(skills):
        if position in settled:
            results.append(settled[position])
            continue
        judgement = judgements.get(position)
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
    job.job_json = {
        **_identity(job),
        "listing": _listing_of(job),
        **extracted.model_dump(),
        # Marks a model reading that can be reused (see `_saved_extraction`).
        "extract_version": matching.EXTRACT_PROMPT_VERSION,
    }
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
        engine_version=MODEL_VERSION,
    )


async def run_match(match_id: uuid.UUID, source: ai_calls.Source = "dashboard") -> None:
    """Runs after the response has been sent, in its own database session.
    `source` is where the check was asked from, for counting its model calls.
    """
    async with get_sessionmaker()() as db:
        match = await repository.get_by_id(db, match_id)
        if match is None or match.status != "pending":
            return
        try:
            with ai_calls.called_by(match.user_id, source):
                await _score(db, match)
        except AppError as exc:
            await db.rollback()
            await _mark_failed(db, match_id, exc.detail)
            await errors_service.record(
                source="job-check", level="warning", exc=exc, message=exc.detail
            )
            return
        except Exception as exc:
            logger.exception("Match %s failed", match_id)
            await db.rollback()
            await _mark_failed(db, match_id, "Scoring failed unexpectedly. Please try again.")
            await errors_service.record(source="job-check", exc=exc, message=str(exc))
            return
        await db.commit()


async def _mark_failed(db: AsyncSession, match_id: uuid.UUID, message: str) -> None:
    match = await repository.get_by_id(db, match_id)
    if match is not None:
        match.status = "failed"
        match.error = message
        await db.commit()
