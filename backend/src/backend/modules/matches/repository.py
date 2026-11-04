import asyncio
import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, selectinload

from backend.modules.matches.models import Job, Match
from backend.modules.profiles.models import Profile


async def find_saved_result(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    job_key: str | None,
    content_hash: str | None,
    engine_versions: Sequence[str],
    key_scored_after: datetime,
    fresh_after: datetime,
) -> Match | None:
    """This user's result for this job and their current profile, if there is
    one to reuse: found by the job's id from its link, or by its exact text.

    One query, job included: the profile's current version is compared inside
    it, so a repeat visit does not have to load the profile first. Every query
    is a round trip to the database, which is what a repeat visit waits on.
    """
    same_job: list[ColumnElement[bool]] = []
    if job_key is not None:
        # An id says nothing about whether the posting was edited, so it is trusted for a while.
        same_job.append(
            and_(Job.job_json["job_key"].astext == job_key, Match.created_at > key_scored_after)
        )
    if content_hash is not None:
        same_job.append(Job.content_hash == content_hash)
    if not same_job:
        return None
    current_version = select(Profile.version).where(Profile.user_id == user_id).scalar_subquery()
    result = await db.execute(
        select(Match)
        .join(Job, Match.job_id == Job.id)
        .where(
            Job.user_id == user_id,
            Match.user_id == user_id,
            or_(*same_job),
            Match.profile_version == current_version,
            or_(
                and_(Match.status == "completed", Match.prompt_versions.in_(engine_versions)),
                and_(Match.status == "pending", Match.created_at > fresh_after),
            ),
        )
        .options(contains_eager(Match.job))
        .order_by(Match.created_at.desc())
        .limit(1)
    )
    return result.unique().scalar_one_or_none()


async def get(db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID) -> Match | None:
    result = await db.execute(
        select(Match)
        .where(Match.id == match_id, Match.user_id == user_id)
        .options(selectinload(Match.job))
    )
    return result.scalar_one_or_none()


# A check scored on the API's own machine is answered before it is saved (see
# `matches.service.Started`), so a request that follows straight away (the resume
# keywords, tracking the job) can arrive first. It waits this long, in steps, for
# the save before deciding the check does not exist.
_SAVE_WAITS_SECONDS = (0.25, 0.5, 0.75, 1.0, 1.5)


async def get_when_saved(db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID) -> Match | None:
    """`get`, but gives a check that is still being saved a moment to arrive."""
    match = await get(db, user_id, match_id)
    for wait in _SAVE_WAITS_SECONDS:
        if match is not None:
            return match
        await asyncio.sleep(wait)
        match = await get(db, user_id, match_id)
    return match


async def get_by_id(db: AsyncSession, match_id: uuid.UUID) -> Match | None:
    """Unscoped lookup for the background runner, which only ever receives ids
    the API created itself. Never call this from a route.
    """
    result = await db.execute(
        select(Match).where(Match.id == match_id).options(selectinload(Match.job))
    )
    return result.scalar_one_or_none()


async def find_job(db: AsyncSession, user_id: uuid.UUID, content_hash: str) -> Job | None:
    result = await db.execute(
        select(Job)
        .where(Job.user_id == user_id, Job.content_hash == content_hash)
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def find_job_by_url(
    db: AsyncSession, user_id: uuid.UUID, url: str, fetched_after: datetime
) -> Job | None:
    """A job already read from this link recently, so the page is not fetched again."""
    result = await db.execute(
        select(Job)
        .where(Job.user_id == user_id, Job.url == url, Job.created_at > fetched_after)
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_rendered_reads(db: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    """How many of this user's jobs were read through the paid page reader."""
    result = await db.execute(
        select(func.count())
        .select_from(Job)
        .where(
            Job.user_id == user_id,
            Job.created_at > since,
            Job.job_json["listing"]["reader"].astext == "rendered",
        )
    )
    return result.scalar_one()


async def count_since(
    db: AsyncSession, user_id: uuid.UUID, since: datetime, *, model_version: str | None = None
) -> int:
    """Checks started since then. With `model_version`, only the ones read by the
    model: finished with that version, or not finished (so not scored locally).
    """
    query = (
        select(func.count())
        .select_from(Match)
        .where(Match.user_id == user_id, Match.created_at > since)
    )
    if model_version is not None:
        query = query.where(
            or_(Match.prompt_versions.is_(None), Match.prompt_versions == model_version)
        )
    result = await db.execute(query)
    return result.scalar_one()


async def list_page(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[Match]:
    query = select(Match).where(Match.user_id == user_id).options(selectinload(Match.job))
    if after:
        created_at, row_id = after
        query = query.where(
            or_(
                Match.created_at < created_at,
                and_(Match.created_at == created_at, Match.id < row_id),
            )
        )
    query = query.order_by(Match.created_at.desc(), Match.id.desc()).limit(limit)
    result = await db.execute(query)
    return list(result.scalars())


async def find_extraction(
    db: AsyncSession, content_hash: str, job_key: str | None, extract_version: int
) -> dict[str, object] | None:
    """What the model read from this job before, by any user: the same text, or
    the same job id from a known site (see `job_key`).

    Deliberately not scoped to a user: only someone holding the same posting can
    reach it, and what is reused (the role, company, years and skills the
    posting names) comes from that public posting, never from anyone's profile
    or score.
    """
    same_job = Job.content_hash == content_hash
    if job_key is not None:
        same_job = or_(same_job, Job.job_json["job_key"].astext == job_key)
    result = await db.execute(
        select(Job.job_json)
        .where(same_job, Job.job_json["extract_version"].astext == str(extract_version))
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def judged_skills(
    db: AsyncSession, user_id: uuid.UUID, profile_version: int, model_version: str, limit: int
) -> list[list[dict[str, object]]]:
    """The skill verdicts of this user's recent model-scored checks against this
    same profile, newest first, so a skill judged once is not judged again.
    """
    result = await db.execute(
        select(Match.skill_results)
        .where(
            Match.user_id == user_id,
            Match.profile_version == profile_version,
            Match.status == "completed",
            Match.prompt_versions == model_version,
        )
        .order_by(Match.created_at.desc())
        .limit(limit)
    )
    return [list(row) for row in result.scalars().all()]
