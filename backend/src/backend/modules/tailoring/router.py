import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.modules.tailoring import service
from backend.modules.tailoring.schemas import (
    KeptRead,
    KeywordCheck,
    TailoredRead,
    TailorRequest,
)
from backend.modules.users.dependencies import get_db_user_or_extension
from backend.modules.users.models import User

router = APIRouter(prefix="/tailored-resumes", tags=["tailored-resumes"])


@router.post("", response_model=TailoredRead)
async def create_tailored_resume(
    payload: TailorRequest,
    # The extension may ask too: the score panel offers this on the job page.
    user: User = Depends(get_db_user_or_extension),
    db: AsyncSession = Depends(get_db),
) -> TailoredRead:
    """Returns a copy of the user's resume with the chosen changes: skills added,
    skills respelled, the headline reworded. This is a preview: nothing is
    stored, and neither the saved resume nor the profile changes.
    Editing is local and takes about a tenth of a second, so there is no
    background job.
    """
    return await service.create(db, user_id=user.id, payload=payload)


@router.get("/keywords", response_model=KeywordCheck)
async def read_keyword_check(
    match_id: uuid.UUID,
    user: User = Depends(get_db_user_or_extension),
    db: AsyncSession = Depends(get_db),
) -> KeywordCheck:
    """Which of the job's words (its title and skills) the user's resume has,
    which it spells differently, and which are missing. No model is called.
    """
    return await service.check_keywords(db, user_id=user.id, match_id=match_id)


@router.post("/keep", response_model=KeptRead)
async def keep_tailored_resume(
    payload: TailorRequest,
    user: User = Depends(get_db_user_or_extension),
    db: AsyncSession = Depends(get_db),
) -> KeptRead:
    """Saves the previewed changes as the user's resume, replacing the one on
    file, and adds the new skills to their profile. Later job checks then see
    those skills in both places.
    """
    return await service.keep(db, user_id=user.id, payload=payload)
