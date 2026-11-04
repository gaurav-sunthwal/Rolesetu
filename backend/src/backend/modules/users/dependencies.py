from fastapi import BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import CurrentUser, get_current_user, require_dashboard_session
from backend.db.session import get_db
from backend.modules.users.models import User
from backend.modules.users.service import count_users, get_or_create_user, send_signup_alert


async def resolve_user(
    db: AsyncSession, current_user: CurrentUser, background_tasks: BackgroundTasks
) -> User:
    """The caller's row, created on their first sign-in. A first sign-in also
    queues the new sign-up alert, which is sent after the response.
    """
    if current_user.user_id is not None:
        # Already loaded into this session while checking the extension key:
        # `get` returns it from memory, without another query.
        known = await db.get(User, current_user.user_id)
        if known is not None:
            return known
    user, created = await get_or_create_user(
        db, firebase_uid=current_user.uid, email=current_user.email
    )
    if created:
        background_tasks.add_task(
            send_signup_alert, user_id=user.id, email=user.email, total_users=await count_users(db)
        )
    return user


async def get_db_user(
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_dashboard_session),
    db: AsyncSession = Depends(get_db),
) -> User:
    """The signed-in dashboard user's database row. Every user-scoped route
    depends on this (or the variant below), so a query can only ever be
    filtered by the caller's own id.
    """
    return await resolve_user(db, current_user, background_tasks)


async def get_db_user_or_extension(
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """As above, but also accepts the user's browser extension. Used only on the
    few routes the extension needs: checking a job, tracking it, reading the profile.
    """
    return await resolve_user(db, current_user, background_tasks)
