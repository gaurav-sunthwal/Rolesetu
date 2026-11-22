import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import and_, case, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.social.models import (
    SocialAccount,
    SocialMetricSnapshot,
    SocialPost,
    SocialPostTarget,
)
from backend.modules.social.platforms.base import Stats

TargetRow = tuple[SocialPostTarget, SocialAccount]


async def list_accounts(db: AsyncSession) -> list[SocialAccount]:
    result = await db.execute(
        select(SocialAccount).order_by(SocialAccount.platform, SocialAccount.name)
    )
    return list(result.scalars())


async def get_accounts(db: AsyncSession, ids: list[uuid.UUID]) -> list[SocialAccount]:
    result = await db.execute(select(SocialAccount).where(SocialAccount.id.in_(ids)))
    return list(result.scalars())


async def upsert_account(
    db: AsyncSession,
    *,
    platform: str,
    external_id: str,
    name: str,
    encrypted_token: str,
    expires_at: datetime | None,
    connected_by: str,
) -> None:
    """Adds the account, or refreshes its token if it was connected before."""
    values = {
        "name": name,
        "access_token": encrypted_token,
        "expires_at": expires_at,
        "connected_by": connected_by,
        "status": "active",
    }
    await db.execute(
        insert(SocialAccount)
        .values(id=uuid.uuid4(), platform=platform, external_id=external_id, **values)
        .on_conflict_do_update(index_elements=["platform", "external_id"], set_=values)
    )


async def delete_account(db: AsyncSession, account_id: uuid.UUID) -> bool:
    result = await db.execute(delete(SocialAccount).where(SocialAccount.id == account_id))
    return bool(result.rowcount)  # type: ignore[attr-defined]


async def mark_account_expired(db: AsyncSession, account_id: uuid.UUID) -> None:
    await db.execute(
        update(SocialAccount).where(SocialAccount.id == account_id).values(status="expired")
    )


async def get_post(db: AsyncSession, post_id: uuid.UUID) -> SocialPost | None:
    return await db.get(SocialPost, post_id)


# The queue: not yet up everywhere it should be. Posted: up somewhere.
QUEUE_STATUSES = ("draft", "scheduled", "publishing", "failed")
POSTED_STATUSES = ("posted", "partly_posted")


async def list_posts(
    db: AsyncSession,
    *,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
    statuses: tuple[str, ...] | None = None,
) -> list[SocialPost]:
    query = select(SocialPost)
    if statuses is not None:
        query = query.where(SocialPost.status.in_(statuses))
    if after is not None:
        created_at, row_id = after
        query = query.where(
            or_(
                SocialPost.created_at < created_at,
                and_(SocialPost.created_at == created_at, SocialPost.id < row_id),
            )
        )
    result = await db.execute(
        query.order_by(SocialPost.created_at.desc(), SocialPost.id.desc()).limit(limit)
    )
    return list(result.scalars())


async def targets_of(
    db: AsyncSession, post_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[TargetRow]]:
    if not post_ids:
        return {}
    result = await db.execute(
        select(SocialPostTarget, SocialAccount)
        .join(SocialAccount, SocialAccount.id == SocialPostTarget.account_id)
        .where(SocialPostTarget.post_id.in_(post_ids))
        .order_by(SocialAccount.platform, SocialAccount.name)
    )
    grouped: dict[uuid.UUID, list[TargetRow]] = defaultdict(list)
    for target, account in result.tuples():
        grouped[target.post_id].append((target, account))
    return grouped


async def replace_targets(
    db: AsyncSession, post_id: uuid.UUID, account_ids: list[uuid.UUID]
) -> None:
    await db.execute(delete(SocialPostTarget).where(SocialPostTarget.post_id == post_id))
    db.add_all(
        SocialPostTarget(id=uuid.uuid4(), post_id=post_id, account_id=account_id)
        for account_id in account_ids
    )


async def claim_due(
    db: AsyncSession, now: datetime, limit: int, only: list[uuid.UUID] | None = None
) -> list[uuid.UUID]:
    """Takes the posts whose time has come, marking them as being published.
    `only` narrows it to some posts (tests use it to leave real ones alone).

    Rows another server is claiming at the same moment are skipped, not
    waited for, so two servers never publish the same post.
    """
    query = select(SocialPost.id).where(
        SocialPost.status == "scheduled", SocialPost.scheduled_at <= now
    )
    if only is not None:
        query = query.where(SocialPost.id.in_(only))
    result = await db.execute(
        query.order_by(SocialPost.scheduled_at).limit(limit).with_for_update(skip_locked=True)
    )
    ids = list(result.scalars())
    if ids:
        await db.execute(
            update(SocialPost).where(SocialPost.id.in_(ids)).values(status="publishing")
        )
    return ids


async def stuck_publishing(
    db: AsyncSession, before: datetime, only: list[uuid.UUID] | None = None
) -> list[uuid.UUID]:
    """Posts left half-published by a server that stopped mid-way."""
    query = select(SocialPost.id).where(
        SocialPost.status == "publishing", SocialPost.updated_at < before
    )
    if only is not None:
        query = query.where(SocialPost.id.in_(only))
    result = await db.execute(query.with_for_update(skip_locked=True))
    return list(result.scalars())


# --- numbers ------------------------------------------------------------------

MEASURED_PLATFORMS = ("instagram", "youtube")


async def targets_needing_numbers(
    db: AsyncSession, *, posted_since: datetime, stale_before: datetime, limit: int
) -> list[TargetRow]:
    """Posted reels and posts whose numbers are missing or older than `stale_before`."""
    result = await db.execute(
        select(SocialPostTarget, SocialAccount)
        .join(SocialAccount, SocialAccount.id == SocialPostTarget.account_id)
        .where(
            SocialPostTarget.status == "posted",
            SocialPostTarget.posted_at >= posted_since,
            SocialPostTarget.external_id.is_not(None),
            SocialAccount.platform.in_(MEASURED_PLATFORMS),
            or_(
                SocialPostTarget.metrics_at.is_(None),
                SocialPostTarget.metrics_at < stale_before,
            ),
        )
        .order_by(SocialPostTarget.metrics_at.asc().nulls_first())
        .limit(limit)
    )
    return list(result.tuples())


async def save_numbers(db: AsyncSession, target_id: uuid.UUID, stats: Stats, at: datetime) -> None:
    await db.execute(
        update(SocialPostTarget)
        .where(SocialPostTarget.id == target_id)
        .values(
            views=stats.views,
            reach=stats.reach,
            likes=stats.likes,
            comments=stats.comments,
            shares=stats.shares,
            saves=stats.saves,
            avg_watch_ms=stats.avg_watch_ms,
            metrics_at=at,
        )
    )
    db.add(
        SocialMetricSnapshot(
            id=uuid.uuid4(),
            target_id=target_id,
            taken_at=at,
            views=stats.views,
            likes=stats.likes,
            comments=stats.comments,
            shares=stats.shares,
        )
    )


async def set_followers(db: AsyncSession, account_id: uuid.UUID, followers: int | None) -> None:
    await db.execute(
        update(SocialAccount).where(SocialAccount.id == account_id).values(followers=followers)
    )


async def totals_by_platform(db: AsyncSession, since: datetime) -> list[dict[str, object]]:
    """Sums of each platform's numbers for posts that went up since `since`."""
    target = SocialPostTarget
    watched = case((target.avg_watch_ms.is_not(None), target.views), else_=0)
    result = await db.execute(
        select(
            SocialAccount.platform,
            func.count(target.id),
            func.coalesce(func.sum(target.views), 0),
            func.coalesce(func.sum(target.reach), 0),
            func.coalesce(func.sum(target.likes), 0),
            func.coalesce(func.sum(target.comments), 0),
            func.coalesce(func.sum(target.shares), 0),
            func.coalesce(func.sum(target.saves), 0),
            func.sum(target.avg_watch_ms * watched),
            func.sum(watched),
        )
        .join(SocialAccount, SocialAccount.id == target.account_id)
        .where(target.status == "posted", target.posted_at >= since)
        .group_by(SocialAccount.platform)
        .order_by(SocialAccount.platform)
    )
    rows: list[dict[str, object]] = []
    for platform, posts, views, reach, likes, comments, shares, saves, ms, weight in result:
        rows.append(
            {
                "platform": platform,
                "posts": posts,
                "views": views,
                "reach": reach,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "saves": saves,
                "avg_watch_seconds": round(ms / weight / 1000, 1) if ms and weight else None,
            }
        )
    return rows


async def last_measured(db: AsyncSession) -> datetime | None:
    result = await db.execute(select(func.max(SocialPostTarget.metrics_at)))
    return result.scalar_one_or_none()


PostedRow = tuple[SocialPost, SocialPostTarget, SocialAccount]


async def posted_targets(db: AsyncSession, limit: int) -> list[PostedRow]:
    """Every target that went up, with its post and account, for the newest `limit` posts."""
    newest = (
        select(SocialPost.id)
        .where(SocialPost.status.in_(POSTED_STATUSES))
        .order_by(SocialPost.created_at.desc())
        .limit(limit)
        .subquery()
    )
    result = await db.execute(
        select(SocialPost, SocialPostTarget, SocialAccount)
        .join(SocialPostTarget, SocialPostTarget.post_id == SocialPost.id)
        .join(SocialAccount, SocialAccount.id == SocialPostTarget.account_id)
        .where(SocialPost.id.in_(select(newest.c.id)), SocialPostTarget.status == "posted")
    )
    return list(result.tuples())


async def snapshots_since(
    db: AsyncSession, target_ids: list[uuid.UUID], since: datetime
) -> dict[uuid.UUID, list[SocialMetricSnapshot]]:
    """Each target's readings taken after `since`, oldest first."""
    if not target_ids:
        return {}
    result = await db.execute(
        select(SocialMetricSnapshot)
        .where(
            SocialMetricSnapshot.target_id.in_(target_ids),
            SocialMetricSnapshot.taken_at >= since,
        )
        .order_by(SocialMetricSnapshot.taken_at)
    )
    grouped: dict[uuid.UUID, list[SocialMetricSnapshot]] = defaultdict(list)
    for snapshot in result.scalars():
        grouped[snapshot.target_id].append(snapshot)
    return grouped


async def queued(db: AsyncSession) -> list[SocialPost]:
    """Scheduled posts, soonest first."""
    result = await db.execute(
        select(SocialPost).where(SocialPost.status == "scheduled").order_by(SocialPost.scheduled_at)
    )
    return list(result.scalars())


async def get_posts(db: AsyncSession, ids: list[uuid.UUID]) -> list[SocialPost]:
    result = await db.execute(select(SocialPost).where(SocialPost.id.in_(ids)))
    return list(result.scalars())
