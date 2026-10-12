from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import CurrentUser, require_dashboard_session
from backend.db.session import get_db
from backend.modules.users.schemas import UserRead
from backend.modules.users.service import get_or_create_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_current_user(
    current_user: CurrentUser = Depends(require_dashboard_session),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    user = await get_or_create_user(db, firebase_uid=current_user.uid, email=current_user.email)
    return UserRead.model_validate(user)
