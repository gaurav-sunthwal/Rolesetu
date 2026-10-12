from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.modules.saved_answers import service
from backend.modules.saved_answers.schemas import QuestionKey, SavedAnswerRead, SavedAnswerWrite
from backend.modules.users.dependencies import get_db_user
from backend.modules.users.models import User

router = APIRouter(prefix="/saved-answers", tags=["saved-answers"])


@router.get("", response_model=list[SavedAnswerRead])
async def list_my_answers(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> list[SavedAnswerRead]:
    rows = await service.list_answers(db, user_id=user.id)
    return [SavedAnswerRead.model_validate(row) for row in rows]


@router.put("/{question_key}", response_model=SavedAnswerRead)
async def set_my_answer(
    question_key: QuestionKey,
    payload: SavedAnswerWrite,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> SavedAnswerRead:
    row = await service.set_answer(
        db, user_id=user.id, question_key=question_key, answer=payload.answer
    )
    return SavedAnswerRead.model_validate(row)


@router.delete("/{question_key}", status_code=204)
async def delete_my_answer(
    question_key: QuestionKey,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_answer(db, user_id=user.id, question_key=question_key)
