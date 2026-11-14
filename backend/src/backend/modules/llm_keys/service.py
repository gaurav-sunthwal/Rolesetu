"""Users' own Gemini keys: retired (ADR 13). AI runs on Rolesetu's keys, limited by
each plan's AI credits. What is left lets the dashboard show and delete a key saved
before; the table is dropped in a later release."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.llm_keys.models import UserLlmKey


async def get_user_llm_key(db: AsyncSession, *, user_id: uuid.UUID) -> UserLlmKey | None:
    result = await db.execute(select(UserLlmKey).where(UserLlmKey.user_id == user_id))
    return result.scalar_one_or_none()


async def delete_user_llm_key(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    row = await get_user_llm_key(db, user_id=user_id)
    if row is not None:
        await db.delete(row)
