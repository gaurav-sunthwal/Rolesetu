from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import CurrentUser, require_dashboard_session
from backend.db.session import get_db
from backend.modules.users.dependencies import resolve_user
from backend.modules.users.schemas import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_current_user(
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_dashboard_session),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    user = await resolve_user(db, current_user, background_tasks)
    return UserRead.model_validate(user)
