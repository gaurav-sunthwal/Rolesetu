import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.social.models import SocialAccount, SocialPost, SocialPostTarget

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


async def list_posts(
    db: AsyncSession, *, after: tuple[datetime, uuid.UUID] | None, limit: int
) -> list[SocialPost]:
    query = select(SocialPost)
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
