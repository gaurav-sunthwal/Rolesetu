"""The admin Payment funnel: how many people reach each step of paying, why payments
fail, who left halfway, and one person's whole payment story."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.billing.models import BillingFunnelEvent

# The steps, in the order people go through them, with what the admin page calls them.
STEPS: list[tuple[str, str]] = [
    ("plan_viewed", "Saw the plan page"),
    ("upgrade_clicked", "Clicked upgrade"),
    ("checkout_opened", "Opened the payment window"),
    ("payment_succeeded", "Paid in the window"),
    ("charge_recorded", "Pro turned on"),
]
_FAILURE_STEPS = ("payment_failed", "verify_failed", "start_failed")
_SUCCESS_STEPS = ("charge_recorded", "autopay_verified", "payment_succeeded")
_AUTOPAY_STEPS = (
    "autopay_charged",
    "autopay_pending",
    "autopay_halted",
    "autopay_cancelled",
    "autopay_completed",
    "autopay_cancel_asked",
    "autopay_stopped",
)


class FunnelStep(BaseModel):
    step: str
    label: str
    users: int


class FailureReason(BaseModel):
    step: str
    reason: str
    count: int
    users: int


class DroppedUser(BaseModel):
    user_id: uuid.UUID
    email: str
    name: str | None
    last_step: str
    last_at: datetime
    last_error: str | None
    reminded_at: datetime | None


class PaymentFunnel(BaseModel):
    period_days: int
    steps: list[FunnelStep]
    failures: list[FailureReason]
    autopay: dict[str, int]
    dropped: list[DroppedUser]


class FunnelEventRead(BaseModel):
    step: str
    source: str
    detail: dict[str, Any]
    created_at: datetime


_STEP_USERS = text(
    """
    SELECT step, count(DISTINCT user_id) FROM billing_funnel_events
    WHERE created_at >= :since GROUP BY step
    """
)

# Razorpay's description is the most useful reason; then its code; then ours.
_FAILURES = text(
    """
    SELECT step,
           coalesce(detail->>'description', detail->>'reason', detail->>'code', 'unknown')
             AS reason,
           count(*) AS n, count(DISTINCT user_id) AS users
    FROM billing_funnel_events
    WHERE created_at >= :since AND step = ANY(:steps)
    GROUP BY 1, 2 ORDER BY n DESC LIMIT 25
    """
)

_DROPPED = text(
    """
    WITH last AS (
        SELECT DISTINCT ON (e.user_id) e.user_id, e.step, e.created_at
        FROM billing_funnel_events e
        WHERE e.created_at >= :since
        ORDER BY e.user_id, e.created_at DESC
    ),
    err AS (
        SELECT DISTINCT ON (e.user_id) e.user_id,
               coalesce(e.detail->>'description', e.detail->>'reason', e.detail->>'code') AS error
        FROM billing_funnel_events e
        WHERE e.created_at >= :since AND e.step = ANY(:failures)
        ORDER BY e.user_id, e.created_at DESC
    )
    SELECT u.id, u.email, coalesce(p.full_name, u.name) AS name, last.step, last.created_at,
           err.error,
           (SELECT max(o.created_at) FROM outreach_emails o
             WHERE o.user_id = u.id AND o.kind = 'payment_reminder') AS reminded_at
    FROM last
    JOIN users u ON u.id = last.user_id
    LEFT JOIN profiles p ON p.user_id = u.id
    LEFT JOIN err ON err.user_id = u.id
    WHERE EXISTS (
        SELECT 1 FROM billing_funnel_events e
        WHERE e.user_id = u.id AND e.created_at >= :since
          AND e.step IN ('upgrade_clicked', 'checkout_opened', 'order_created', 'autopay_created')
    )
      AND NOT EXISTS (
        SELECT 1 FROM billing_funnel_events e
        WHERE e.user_id = u.id AND e.created_at >= :since AND e.step = ANY(:successes)
    )
    ORDER BY last.created_at DESC
    LIMIT 100
    """
)


async def funnel(db: AsyncSession, *, days: int) -> PaymentFunnel:
    since = datetime.now(UTC) - timedelta(days=days)
    counts = {
        step: int(users) for step, users in (await db.execute(_STEP_USERS, {"since": since})).all()
    }
    # Someone whose Pro turned on counts as having paid, even if the browser's own
    # report of it was lost (a closed tab).
    counts["payment_succeeded"] = max(
        counts.get("payment_succeeded", 0), counts.get("charge_recorded", 0)
    )
    failures = [
        FailureReason(step=step, reason=str(reason)[:200], count=int(n), users=int(users))
        for step, reason, n, users in (
            await db.execute(_FAILURES, {"since": since, "steps": list(_FAILURE_STEPS)})
        ).all()
    ]
    dropped = [
        DroppedUser(
            user_id=row.id,
            email=row.email,
            name=row.name,
            last_step=row.step,
            last_at=row.created_at,
            last_error=row.error,
            reminded_at=row.reminded_at,
        )
        for row in (
            await db.execute(
                _DROPPED,
                {
                    "since": since,
                    "failures": list(_FAILURE_STEPS),
                    "successes": list(_SUCCESS_STEPS),
                },
            )
        ).all()
    ]
    return PaymentFunnel(
        period_days=days,
        steps=[FunnelStep(step=s, label=label, users=counts.get(s, 0)) for s, label in STEPS],
        failures=failures,
        autopay={step: counts.get(step, 0) for step in _AUTOPAY_STEPS},
        dropped=dropped,
    )


async def timeline(db: AsyncSession, *, user_id: uuid.UUID) -> list[FunnelEventRead]:
    result = await db.execute(
        select(BillingFunnelEvent)
        .where(BillingFunnelEvent.user_id == user_id)
        .order_by(BillingFunnelEvent.created_at.desc())
        .limit(200)
    )
    return [
        FunnelEventRead(
            step=event.step, source=event.source, detail=event.detail, created_at=event.created_at
        )
        for event in result.scalars()
    ]
