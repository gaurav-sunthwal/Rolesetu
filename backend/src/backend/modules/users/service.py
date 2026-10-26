import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.email import send_email
from backend.modules.users import emails
from backend.modules.users.models import User

logger = logging.getLogger(__name__)


async def get_or_create_user(
    db: AsyncSession, *, firebase_uid: str, email: str | None
) -> tuple[User, bool]:
    """Every authenticated request resolves to a row here. Returns the user and
    whether this request created it (their first sign-in).

    Almost always the user exists, so that is a single read. Only a first
    sign-in inserts, and it does so as an upsert because the dashboard fires
    several requests at once then; a plain insert would have two of them race
    and one fail on the unique constraint. Only the request whose insert
    landed gets a row back from RETURNING, so exactly one of them sees `True`.
    """
    by_uid = select(User).where(User.firebase_uid == firebase_uid)
    user = (await db.execute(by_uid)).scalar_one_or_none()
    if user is not None:
        return user, False

    inserted = await db.execute(
        insert(User)
        .values(firebase_uid=firebase_uid, email=email or f"{firebase_uid}@unknown.local")
        .on_conflict_do_nothing(index_elements=[User.firebase_uid])
        .returning(User.id)
    )
    created = inserted.scalar_one_or_none() is not None
    return (await db.execute(by_uid)).scalar_one(), created


async def count_users(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(User))).scalar_one()


async def send_signup_alert(*, user_id: uuid.UUID, email: str, total_users: int) -> None:
    """Tells the addresses in SIGNUP_ALERT_EMAILS that someone new signed up.
    Runs after the reply has gone out, so a slow or failing mail service never
    holds up or breaks the new user's first page load.
    """
    recipients = get_settings().signup_alert_emails
    message = emails.new_user_alert(
        email=email, signed_up_at=datetime.now(UTC), total_users=total_users
    )
    for recipient in recipients:
        try:
            await send_email(
                to=recipient,
                subject=message.subject,
                html=message.html,
                text=message.text,
                # Resend sends a given key once, so a first request that is
                # retried after a rollback cannot alert twice.
                idempotency_key=f"signup-alert-{user_id}-{recipient}",
            )
        except Exception:
            logger.exception("New sign-up alert was not sent")
