from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.users.models import User


async def get_or_create_user(db: AsyncSession, *, firebase_uid: str, email: str | None) -> User:
    """Every authenticated request resolves to a row here.

    Almost always the user exists, so that is a single read. Only a first
    sign-in inserts, and it does so as an upsert because the dashboard fires
    several requests at once then; a plain insert would have two of them race
    and one fail on the unique constraint.
    """
    by_uid = select(User).where(User.firebase_uid == firebase_uid)
    user = (await db.execute(by_uid)).scalar_one_or_none()
    if user is not None:
        return user

    await db.execute(
        insert(User)
        .values(firebase_uid=firebase_uid, email=email or f"{firebase_uid}@unknown.local")
        .on_conflict_do_nothing(index_elements=[User.firebase_uid])
    )
    return (await db.execute(by_uid)).scalar_one()
