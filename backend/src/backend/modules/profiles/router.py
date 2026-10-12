from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.modules.profiles import service
from backend.modules.profiles.schemas import ProfileRead, ProfileWrite
from backend.modules.users.dependencies import get_db_user, get_db_user_or_extension
from backend.modules.users.models import User

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=ProfileRead)
async def read_my_profile(
    user: User = Depends(get_db_user_or_extension), db: AsyncSession = Depends(get_db)
) -> ProfileRead:
    return await service.get_profile(db, user_id=user.id)


@router.put("/me", response_model=ProfileRead)
async def save_my_profile(
    payload: ProfileWrite,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileRead:
    return await service.save_profile(db, user_id=user.id, payload=payload)
