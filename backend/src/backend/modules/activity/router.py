from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.modules.activity import service
from backend.modules.activity.schemas import ActivityYear
from backend.modules.users.dependencies import get_db_user
from backend.modules.users.models import User

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/me", response_model=ActivityYear)
async def my_activity(
    tz: Annotated[str | None, Query(max_length=64)] = None,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> ActivityYear:
    """Your activity per day over the last year, with your streaks. `tz` is your
    time zone (e.g. Asia/Kolkata); unknown names fall back to UTC."""
    return await service.year(db, user_id=user.id, timezone=tz)
