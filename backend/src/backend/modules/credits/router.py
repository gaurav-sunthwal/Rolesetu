from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.modules.credits import service
from backend.modules.credits.schemas import CreditsRead
from backend.modules.users.dependencies import get_db_user_or_extension
from backend.modules.users.models import User

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/me", response_model=CreditsRead)
async def my_credits(
    user: User = Depends(get_db_user_or_extension), db: AsyncSession = Depends(get_db)
) -> CreditsRead:
    """This month's AI credits: used, left, and when they come back."""
    return await service.usage(db, user_id=user.id)
