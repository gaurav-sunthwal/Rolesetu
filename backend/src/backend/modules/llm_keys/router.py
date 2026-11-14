from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import GoneError
from backend.db.session import get_db
from backend.modules.llm_keys.schemas import LlmKeySet, LlmKeyStatus
from backend.modules.llm_keys.service import delete_user_llm_key, get_user_llm_key
from backend.modules.users.dependencies import get_db_user
from backend.modules.users.models import User

router = APIRouter(prefix="/llm-keys", tags=["llm-keys"])


@router.get("/me", response_model=LlmKeyStatus)
async def read_my_llm_key_status(
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> LlmKeyStatus:
    row = await get_user_llm_key(db, user_id=user.id)
    return LlmKeyStatus(has_key=row is not None, updated_at=row.updated_at if row else None)


@router.put("/me", response_model=LlmKeyStatus, deprecated=True)
async def set_my_llm_key(payload: LlmKeySet, user: User = Depends(get_db_user)) -> LlmKeyStatus:
    """Retired: keys are no longer saved. Kept for one release so an open, older
    dashboard gets a clear answer instead of a missing page."""
    raise GoneError(
        "Your own Gemini key is no longer needed. AI now comes with your plan's monthly"
        " AI credits; see Plan in Settings."
    )


@router.delete("/me", status_code=204)
async def delete_my_llm_key(
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_user_llm_key(db, user_id=user.id)
