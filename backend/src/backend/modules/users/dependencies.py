from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import CurrentUser, get_current_user, require_dashboard_session
from backend.db.session import get_db
from backend.modules.users.models import User
from backend.modules.users.service import get_or_create_user


async def get_db_user(
    current_user: CurrentUser = Depends(require_dashboard_session),
    db: AsyncSession = Depends(get_db),
) -> User:
    """The signed-in dashboard user's database row. Every user-scoped route
    depends on this (or the variant below), so a query can only ever be
    filtered by the caller's own id.
    """
    return await get_or_create_user(db, firebase_uid=current_user.uid, email=current_user.email)


async def get_db_user_or_extension(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """As above, but also accepts the user's browser extension. Used only on the
    few routes the extension needs: checking a job, tracking it, reading the profile.
    """
    return await get_or_create_user(db, firebase_uid=current_user.uid, email=current_user.email)
