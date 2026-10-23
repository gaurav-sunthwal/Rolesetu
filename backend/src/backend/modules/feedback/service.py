"""Writes to people once, a few hours after they first sign in: thanks, and
either a word about the extension (if they have not connected it) or how has
it been so far (if they have). Runs on a timer inside the API (see `run_forever`), not for a
request.

Each email is written to outreach_emails before it is sent. A server that
stops halfway may then miss one email, but can never send the same person a
second one, which matters more for a note like this.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from backend.core.config import get_settings
from backend.core.email import is_configured as email_is_configured
from backend.core.email import send_email
from backend.db.session import get_sessionmaker
from backend.modules.admin.models import OutreachEmail
from backend.modules.feedback import emails, repository

logger = logging.getLogger(__name__)

CHECK_EVERY = timedelta(minutes=10)
# People who signed up longer ago than this are left alone, so turning the
# feature on does not write to everyone who joined weeks ago.
TOO_OLD_AFTER = timedelta(days=3)
# Well under Gmail's 500 a day, and keeps one round short.
MAX_PER_ROUND = 25


async def send_due(now: datetime | None = None) -> int:
    """Sends the emails that are due. Returns how many were sent."""
    if not email_is_configured():
        return 0
    now = now or datetime.now(UTC)
    delay = timedelta(hours=get_settings().feedback_email_delay_hours)
    sessionmaker = get_sessionmaker()

    async with sessionmaker() as db:
        if not await repository.take_lock(db):
            return 0  # Another server instance is doing this round.
        people = await repository.due(
            db,
            joined_before=now - delay,
            joined_after=now - TOO_OLD_AFTER,
            limit=MAX_PER_ROUND,
        )
        store_url = get_settings().extension_store_url
        messages = [
            emails.first_use_feedback(
                full_name=person.name, has_extension=person.has_extension, store_url=store_url
            )
            for person in people
        ]
        records = [
            OutreachEmail(
                id=uuid.uuid4(),
                user_id=person.user_id,
                admin_email=repository.SENT_BY,
                kind=repository.FEEDBACK,
                subject=message.subject[:200],
                status="sending",
            )
            for person, message in zip(people, messages, strict=True)
        ]
        db.add_all(records)
        await db.commit()

    sent = 0
    for record, message, person in zip(records, messages, people, strict=True):
        try:
            await send_email(
                to=person.email,
                subject=message.subject,
                html=None,
                text=message.text,
                idempotency_key=f"feedback-{record.id}",
                sender_name=emails.SENDER_NAME,
            )
            record.status = "sent"
            sent += 1
        except Exception as exc:
            logger.warning(
                "feedback email to user=%s failed: %s", person.user_id, type(exc).__name__
            )
            record.status = "failed"
            record.error = "The email service refused or did not answer."
        async with sessionmaker() as db:
            await db.merge(record)
            await db.commit()
    return sent


async def run_forever() -> None:
    """Checks for due emails every few minutes, for as long as the server runs."""
    while True:
        try:
            sent = await send_due()
            if sent:
                logger.info("feedback emails sent: %d", sent)
        except Exception:
            logger.exception("feedback email round failed")
        await asyncio.sleep(CHECK_EVERY.total_seconds())
