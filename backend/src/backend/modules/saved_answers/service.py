import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import ValidationFailedError
from backend.modules.saved_answers import repository
from backend.modules.saved_answers.models import SavedAnswer

MAX_ANSWERS_PER_USER = 50


async def list_answers(db: AsyncSession, *, user_id: uuid.UUID) -> list[SavedAnswer]:
    return await repository.list_for_user(db, user_id)


async def set_answer(
    db: AsyncSession, *, user_id: uuid.UUID, question_key: str, answer: str
) -> SavedAnswer:
    row = await repository.get(db, user_id, question_key)
    if row is None:
        if await repository.count_for_user(db, user_id) >= MAX_ANSWERS_PER_USER:
            raise ValidationFailedError(
                f"You can save up to {MAX_ANSWERS_PER_USER} answers. Remove one to add another."
            )
        row = SavedAnswer(user_id=user_id, question_key=question_key, answer=answer)
        db.add(row)
    else:
        row.answer = answer
    await db.flush()
    await db.refresh(row)
    return row


async def delete_answer(db: AsyncSession, *, user_id: uuid.UUID, question_key: str) -> None:
    await repository.remove(db, user_id, question_key)
