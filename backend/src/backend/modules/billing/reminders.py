"""Emails about payments that did not finish, sent on a timer inside the API.

- Someone opened the payment window and left without paying: one reminder, an hour
  later (`PAYMENT_REMINDER`). At most once a week, never once they are on Pro.
- Someone's autopay renewal failed (Razorpay is retrying, or gave up): one note
  asking them to update how they pay (`AUTOPAY_FAILED`). At most once a week.

Each email is written to outreach_emails before it is sent, so a server that stops
halfway can miss one but never send twice. A database lock lets one API instance
send at a time. Both kinds are plain text from the founder, like the other notes.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import TextClause, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.email import is_configured as email_is_configured
from backend.core.email import send_email
from backend.db.session import get_sessionmaker
from backend.modules.admin.emails import SENDER_NAME
from backend.modules.admin.models import OutreachEmail

logger = logging.getLogger(__name__)

PAYMENT_REMINDER = "payment_reminder"
AUTOPAY_FAILED = "autopay_failed"
SENT_BY = "automatic"
# Hourly: each check wakes the database, and Neon's free plan bills the time it is awake.
CHECK_EVERY = timedelta(hours=1)
ONCE_PER = timedelta(days=7)
# Older drop-offs are left alone, so turning this on does not write to everyone
# who ever opened the payment window.
NOT_AFTER = timedelta(hours=48)
MAX_PER_ROUND = 25
_LOCK_KEY = 8_241_506_317

# Opened the payment window (or had an order or mandate made) between `older` and
# `newer`, with nothing paid since, not on Pro now, and no reminder this week.
_DROPPED_OFF = text(
    """
    SELECT u.id, u.email, coalesce(p.full_name, u.name) AS name
    FROM users u
    LEFT JOIN profiles p ON p.user_id = u.id
    WHERE EXISTS (
        SELECT 1 FROM billing_funnel_events e
        WHERE e.user_id = u.id
          AND e.step IN ('checkout_opened', 'order_created', 'autopay_created')
          AND e.created_at BETWEEN :older AND :newer
    )
      AND NOT EXISTS (
        SELECT 1 FROM billing_funnel_events e
        WHERE e.user_id = u.id
          AND e.step IN ('charge_recorded', 'autopay_verified', 'payment_succeeded')
          AND e.created_at >= :older
    )
      AND NOT EXISTS (
        SELECT 1 FROM billing_orders b
        WHERE b.user_id = u.id AND b.status = 'paid'
          AND b.pro_starts_at <= now() AND b.pro_ends_at > now()
    )
      AND NOT EXISTS (
        SELECT 1 FROM outreach_emails o
        WHERE o.user_id = u.id AND o.kind = :kind AND o.created_at >= :week_ago
    )
    ORDER BY u.id
    LIMIT :limit
    """
)

# An autopay Razorpay is retrying ("pending") or gave up on ("halted") in the last
# few days, with no note about it this week.
_RENEWAL_FAILED = text(
    """
    SELECT DISTINCT ON (u.id) u.id, u.email, coalesce(p.full_name, u.name) AS name
    FROM billing_subscriptions s
    JOIN users u ON u.id = s.user_id
    LEFT JOIN profiles p ON p.user_id = u.id
    WHERE s.status IN ('pending', 'halted')
      AND s.updated_at >= :older
      AND NOT EXISTS (
        SELECT 1 FROM outreach_emails o
        WHERE o.user_id = u.id AND o.kind = :kind AND o.created_at >= :week_ago
    )
    ORDER BY u.id
    LIMIT :limit
    """
)


@dataclass(frozen=True)
class _Person:
    user_id: uuid.UUID
    email: str
    first_name: str


@dataclass(frozen=True)
class _Note:
    subject: str
    text: str


def payment_reminder(first_name: str, plan_url: str) -> _Note:
    hello = f"Hi {first_name}," if first_name else "Hi,"
    return _Note(
        subject="Your Rolesetu Pro upgrade did not finish",
        text=(
            f"{hello}\n\n"
            "You started upgrading to Rolesetu Pro but the payment did not go through, so"
            " nothing was charged.\n\n"
            "If something went wrong (a UPI app that did not open, a card that was declined,"
            " or the page just got stuck), reply to this email and tell me. I read every"
            " reply myself and will help.\n\n"
            f"You can pick up where you left off here: {plan_url}\n\n"
            "Thanks,\nGaurav Sunthwal\nFounder, Rolesetu\n\n"
            "You are getting this once because you opened the payment screen. Rolesetu will"
            " not remind you again this week."
        ),
    )


def autopay_failed(first_name: str, plan_url: str) -> _Note:
    hello = f"Hi {first_name}," if first_name else "Hi,"
    return _Note(
        subject="Your Rolesetu Pro renewal did not go through",
        text=(
            f"{hello}\n\n"
            "This month's autopay payment for Rolesetu Pro did not go through. Razorpay may"
            " try again over the next few days. If your UPI mandate or card has changed, set"
            " up autopay again so your Pro keeps running.\n\n"
            f"Your plan: {plan_url}\n\n"
            "Your Pro stays on until the end of the month you already paid for. Reply to this"
            " email if anything looks wrong and I will sort it out.\n\n"
            "Thanks,\nGaurav Sunthwal\nFounder, Rolesetu"
        ),
    )


def _first_name(name: str | None) -> str:
    return (name or "").strip().split(" ")[0][:40]


async def _take_lock(db: AsyncSession) -> bool:
    result = await db.execute(select(func.pg_try_advisory_xact_lock(_LOCK_KEY)))
    return bool(result.scalar_one())


async def _due(
    db: AsyncSession, query: TextClause, kind: str, older: datetime, newer: datetime, now: datetime
) -> list[_Person]:
    rows = await db.execute(
        query,
        {
            "older": older,
            "newer": newer,
            "kind": kind,
            "week_ago": now - ONCE_PER,
            "limit": MAX_PER_ROUND,
        },
    )
    return [_Person(row.id, row.email, _first_name(row.name)) for row in rows]


async def send_due(now: datetime | None = None) -> int:
    """Sends the reminders that are due. Returns how many were sent."""
    if not email_is_configured():
        return 0
    now = now or datetime.now(UTC)
    settings = get_settings()
    plan_url = f"{settings.dashboard_url.rstrip('/')}/app/plan"
    delay = timedelta(minutes=settings.payment_reminder_after_minutes)
    sessionmaker = get_sessionmaker()

    async with sessionmaker() as db:
        if not await _take_lock(db):
            return 0  # another server is doing this round
        dropped = await _due(db, _DROPPED_OFF, PAYMENT_REMINDER, now - NOT_AFTER, now - delay, now)
        failed = await _due(db, _RENEWAL_FAILED, AUTOPAY_FAILED, now - timedelta(days=3), now, now)
        batch: list[tuple[OutreachEmail, _Note, _Person]] = []
        for kind, people, write in (
            (PAYMENT_REMINDER, dropped, payment_reminder),
            (AUTOPAY_FAILED, failed, autopay_failed),
        ):
            for person in people:
                note = write(person.first_name, plan_url)
                record = OutreachEmail(
                    id=uuid.uuid4(),
                    user_id=person.user_id,
                    admin_email=SENT_BY,
                    kind=kind,
                    subject=note.subject[:200],
                    status="sending",
                )
                batch.append((record, note, person))
        db.add_all([record for record, _, _ in batch])
        await db.commit()

    sent = 0
    for record, note, person in batch:
        try:
            await send_email(
                to=person.email,
                subject=note.subject,
                html=None,
                text=note.text,
                idempotency_key=f"{record.kind}-{record.id}",
                sender_name=SENDER_NAME,
            )
            record.status = "sent"
            sent += 1
        except Exception as exc:
            logger.warning(
                "%s email to user=%s failed: %s", record.kind, person.user_id, type(exc).__name__
            )
            record.status = "failed"
            record.error = "The email service refused or did not answer."
        async with sessionmaker() as db:
            await db.merge(record)
            await db.commit()
    return sent


async def run_forever() -> None:
    """Checks for due reminders every hour, for as long as the server runs."""
    while True:
        try:
            if sent := await send_due():
                logger.info("payment reminder emails sent: %d", sent)
        except Exception:
            logger.exception("payment reminder round failed")
        await asyncio.sleep(CHECK_EVERY.total_seconds())
