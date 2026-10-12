import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.saved_answers.models import SavedAnswer


async def list_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[SavedAnswer]:
    result = await db.execute(
        select(SavedAnswer).where(SavedAnswer.user_id == user_id).order_by(SavedAnswer.question_key)
    )
    return list(result.scalars())


async def get(db: AsyncSession, user_id: uuid.UUID, question_key: str) -> SavedAnswer | None:
    result = await db.execute(
        select(SavedAnswer).where(
            SavedAnswer.user_id == user_id, SavedAnswer.question_key == question_key
        )
    )
    return result.scalar_one_or_none()


async def count_for_user(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(SavedAnswer).where(SavedAnswer.user_id == user_id)
    )
    return result.scalar_one()


async def remove(db: AsyncSession, user_id: uuid.UUID, question_key: str) -> None:
    await db.execute(
        delete(SavedAnswer).where(
            SavedAnswer.user_id == user_id, SavedAnswer.question_key == question_key
        )
    )
