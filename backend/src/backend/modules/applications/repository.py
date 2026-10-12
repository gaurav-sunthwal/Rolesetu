import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.modules.applications.models import Application


async def get(
    db: AsyncSession, user_id: uuid.UUID, application_id: uuid.UUID, *, with_events: bool = False
) -> Application | None:
    query = select(Application).where(
        Application.id == application_id, Application.user_id == user_id
    )
    if with_events:
        query = query.options(selectinload(Application.events))
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_by_idempotency_key(
    db: AsyncSession, user_id: uuid.UUID, key: str
) -> Application | None:
    result = await db.execute(
        select(Application).where(
            Application.user_id == user_id, Application.idempotency_key == key
        )
    )
    return result.scalar_one_or_none()


async def list_page(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: str | None,
    search: str | None,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[Application]:
    query = select(Application).where(Application.user_id == user_id)
    if status:
        query = query.where(Application.status == status)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(Application.role.ilike(pattern), Application.company.ilike(pattern))
        )
    if after:
        created_at, row_id = after
        query = query.where(
            or_(
                Application.created_at < created_at,
                and_(Application.created_at == created_at, Application.id < row_id),
            )
        )
    query = query.order_by(Application.created_at.desc(), Application.id.desc()).limit(limit)
    result = await db.execute(query)
    return list(result.scalars())


async def count_by_status(db: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    result = await db.execute(
        select(Application.status, func.count())
        .where(Application.user_id == user_id)
        .group_by(Application.status)
    )
    return {status: count for status, count in result.all()}


async def count_follow_ups_due(db: AsyncSession, user_id: uuid.UUID, before: datetime) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Application)
        .where(
            Application.user_id == user_id,
            Application.status == "applied",
            Application.applied_at <= before,
        )
    )
    return result.scalar_one()
