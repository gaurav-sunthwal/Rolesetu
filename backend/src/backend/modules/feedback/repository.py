"""Finds who is owed the first-use feedback email.

This reads across every user's rows, like the admin repository: it runs on
the server's own schedule, never for a request, so there is no caller to
scope it to.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.admin.models import OutreachEmail
from backend.modules.extension.models import ExtensionToken
from backend.modules.profiles.models import Profile
from backend.modules.users.models import User

FEEDBACK = "first_use_feedback"
# Stored in outreach_emails.admin_email for emails the server sends by itself.
SENT_BY = "automatic"

# One number shared by every server instance, so only one of them picks
# recipients at a time (a Postgres advisory lock, released at commit).
_LOCK_KEY = 0x5E7F_EEDB


@dataclass(frozen=True)
class Recipient:
    user_id: uuid.UUID
    email: str
    name: str | None
    has_extension: bool


async def take_lock(db: AsyncSession) -> bool:
    result = await db.execute(select(func.pg_try_advisory_xact_lock(_LOCK_KEY)))
    return bool(result.scalar_one())


async def due(
    db: AsyncSession, *, joined_before: datetime, joined_after: datetime, limit: int
) -> list[Recipient]:
    """People who first signed in between the two times and have never been
    sent this email, oldest first.
    """
    already_asked = exists(
        select(OutreachEmail.id).where(
            OutreachEmail.user_id == User.id, OutreachEmail.kind == FEEDBACK
        )
    )
    has_extension = exists(select(ExtensionToken.id).where(ExtensionToken.user_id == User.id))
    result = await db.execute(
        select(User.id, User.email, func.coalesce(Profile.full_name, User.name), has_extension)
        .outerjoin(Profile, Profile.user_id == User.id)
        .where(
            User.created_at <= joined_before,
            User.created_at > joined_after,
            # Accounts made without an email address get a placeholder one.
            ~User.email.endswith("@unknown.local"),
            ~already_asked,
        )
        .order_by(User.created_at)
        .limit(limit)
    )
    return [Recipient(row[0], row[1], row[2], bool(row[3])) for row in result]
