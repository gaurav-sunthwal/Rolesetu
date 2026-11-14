"""Every step on the way to paying, and everything that went wrong on it.

The dashboard reports what only the browser sees (the plan page shown, the payment
window opened or closed, Razorpay's reason for a failed payment). The server adds
what only it sees (orders and subscriptions made, Razorpay unreachable, a payment
that did not verify) and what Razorpay's webhooks say (charged, retrying, stopped).
The admin Payment funnel and the reminder emails read these rows.
"""

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import RateLimitedError
from backend.db.session import get_sessionmaker
from backend.modules.billing.models import BillingFunnelEvent

logger = logging.getLogger(__name__)

# What the dashboard may report. Anything else is refused.
ClientStep = Literal[
    "plan_viewed",
    "upgrade_clicked",
    "checkout_opened",
    "checkout_closed",
    "payment_failed",
    "payment_succeeded",
    "verify_failed",
    "one_time_chosen",
]

MAX_CLIENT_EVENTS_PER_HOUR = 120
_DETAIL_KEYS = 12
_DETAIL_CHARS = 300
_KEY = re.compile(r"^[a-z_]{1,32}$")


class FunnelEventWrite(BaseModel):
    step: ClientStep
    attempt_id: uuid.UUID | None = None
    # Razorpay's error code, reason, step and source, the payment method... Small
    # and flat: a few short values, never a card or account number.
    detail: dict[str, str | int | bool | None] = Field(default_factory=dict)

    @field_validator("detail")
    @classmethod
    def small_and_flat(
        cls, value: dict[str, str | int | bool | None]
    ) -> dict[str, str | int | bool | None]:
        if len(value) > _DETAIL_KEYS:
            raise ValueError("Too many details.")
        cleaned: dict[str, str | int | bool | None] = {}
        for key, item in value.items():
            if not _KEY.fullmatch(key):
                raise ValueError("Detail names are lower-case words.")
            cleaned[key] = item[:_DETAIL_CHARS] if isinstance(item, str) else item
        return cleaned


def record(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    step: str,
    source: Literal["client", "server", "webhook"],
    attempt_id: uuid.UUID | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Adds one event to the caller's transaction (written when it commits)."""
    db.add(
        BillingFunnelEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            attempt_id=attempt_id,
            step=step[:32],
            source=source,
            detail=detail or {},
        )
    )


async def record_failure(
    *,
    user_id: uuid.UUID,
    step: str,
    attempt_id: uuid.UUID | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Writes a failure in its own transaction: the request that failed rolls its
    own back, and the failure is exactly what the funnel must not lose. Never raises."""
    try:
        async with get_sessionmaker()() as db:
            record(
                db,
                user_id=user_id,
                step=step,
                source="server",
                attempt_id=attempt_id,
                detail=detail,
            )
            await db.commit()
    except Exception:
        logger.exception("Could not record funnel failure %s", step)


async def record_from_client(
    db: AsyncSession, *, user_id: uuid.UUID, event: FunnelEventWrite
) -> None:
    since = datetime.now(UTC) - timedelta(hours=1)
    recent = await db.execute(
        select(func.count())
        .select_from(BillingFunnelEvent)
        .where(
            BillingFunnelEvent.user_id == user_id,
            BillingFunnelEvent.source == "client",
            BillingFunnelEvent.created_at >= since,
        )
    )
    if int(recent.scalar_one()) >= MAX_CLIENT_EVENTS_PER_HOUR:
        raise RateLimitedError("Too many events. Please slow down.")
    record(
        db,
        user_id=user_id,
        step=event.step,
        source="client",
        attempt_id=event.attempt_id,
        detail=event.detail,
    )
