import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.extension.models import ExtensionToken
from backend.modules.users.models import User

TOKEN_PREFIX = "aa_ext_"
# Recording every use would add a write to each request; once an hour is enough
# to show the user whether the extension is still active.
_TOUCH_EVERY = timedelta(hours=1)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def connect(db: AsyncSession, *, user_id: uuid.UUID) -> tuple[str, ExtensionToken]:
    """Issues a new key, replacing any earlier one (which stops working)."""
    await db.execute(delete(ExtensionToken).where(ExtensionToken.user_id == user_id))
    token = f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    row = ExtensionToken(user_id=user_id, token_hash=_hash(token))
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return token, row


async def get_connection(db: AsyncSession, *, user_id: uuid.UUID) -> ExtensionToken | None:
    result = await db.execute(select(ExtensionToken).where(ExtensionToken.user_id == user_id))
    return result.scalar_one_or_none()


async def disconnect(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    await db.execute(delete(ExtensionToken).where(ExtensionToken.user_id == user_id))


async def user_for_token(db: AsyncSession, token: str) -> User | None:
    result = await db.execute(
        select(User, ExtensionToken)
        .join(ExtensionToken, ExtensionToken.user_id == User.id)
        .where(ExtensionToken.token_hash == _hash(token))
    )
    found = result.first()
    if found is None:
        return None
    user, row = found
    now = datetime.now(UTC)
    if row.last_used_at is None or row.last_used_at < now - _TOUCH_EVERY:
        row.last_used_at = now
    return user
