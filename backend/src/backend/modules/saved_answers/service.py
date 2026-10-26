import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import ValidationFailedError
from backend.modules.saved_answers import repository
from backend.modules.saved_answers.models import SavedAnswer

# Room for the questions autofill learns from forms, on top of the common ones.
MAX_ANSWERS_PER_USER = 200


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


async def learn_answers(
    db: AsyncSession, *, user_id: uuid.UUID, answers: list[tuple[str, str]]
) -> list[tuple[str, str | None]]:
    """Saves answers the user typed into a form, so the next form can be filled
    with them. Returns each key that changed with its previous answer. Unlike
    `set_answer`, a full list is not an error: the user is mid-application,
    so a new question is quietly not remembered instead.
    """
    learned: list[tuple[str, str | None]] = []
    count = await repository.count_for_user(db, user_id)
    for question_key, answer in answers:
        row = await repository.get(db, user_id, question_key)
        if row is None:
            if count >= MAX_ANSWERS_PER_USER:
                continue
            db.add(SavedAnswer(user_id=user_id, question_key=question_key, answer=answer))
            count += 1
            learned.append((question_key, None))
        elif row.answer != answer:
            learned.append((question_key, row.answer))
            row.answer = answer
    await db.flush()
    return learned


async def delete_answer(db: AsyncSession, *, user_id: uuid.UUID, question_key: str) -> None:
    await repository.remove(db, user_id, question_key)
