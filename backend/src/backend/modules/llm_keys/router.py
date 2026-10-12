from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import CurrentUser, require_dashboard_session
from backend.db.session import get_db
from backend.modules.llm_keys.schemas import LlmKeySet, LlmKeyStatus
from backend.modules.llm_keys.service import (
    delete_user_llm_key,
    get_user_llm_key,
    set_user_llm_key,
)
from backend.modules.users.service import get_or_create_user

router = APIRouter(prefix="/llm-keys", tags=["llm-keys"])


@router.get("/me", response_model=LlmKeyStatus)
async def read_my_llm_key_status(
    current_user: CurrentUser = Depends(require_dashboard_session),
    db: AsyncSession = Depends(get_db),
) -> LlmKeyStatus:
    user = await get_or_create_user(db, firebase_uid=current_user.uid, email=current_user.email)
    row = await get_user_llm_key(db, user_id=user.id)
    return LlmKeyStatus(has_key=row is not None, updated_at=row.updated_at if row else None)


@router.put("/me", response_model=LlmKeyStatus)
async def set_my_llm_key(
    payload: LlmKeySet,
    current_user: CurrentUser = Depends(require_dashboard_session),
    db: AsyncSession = Depends(get_db),
) -> LlmKeyStatus:
    user = await get_or_create_user(db, firebase_uid=current_user.uid, email=current_user.email)
    row = await set_user_llm_key(db, user_id=user.id, api_key=payload.api_key)
    return LlmKeyStatus(has_key=True, updated_at=row.updated_at)


@router.delete("/me", status_code=204)
async def delete_my_llm_key(
    current_user: CurrentUser = Depends(require_dashboard_session),
    db: AsyncSession = Depends(get_db),
) -> None:
    user = await get_or_create_user(db, firebase_uid=current_user.uid, email=current_user.email)
    await delete_user_llm_key(db, user_id=user.id)
