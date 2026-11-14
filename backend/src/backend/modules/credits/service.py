"""AI credits: how much of Rolesetu's paid model use each plan includes.

Every action that calls a paid model spends credits *before* the call, inside the
request's transaction. If the call fails, the request rolls back and the credits
come back with it; nothing has to remember to refund them. Work that runs after
the request (a background job check) gives them back itself on failure.

Free work (scoring with the local engine, autofill, templates, tracking) never
costs credits. Neither does reading a resume, so nobody is locked out of
starting.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import PlanLimitError
from backend.modules.billing.service import is_pro
from backend.modules.credits import repository
from backend.modules.credits.schemas import CreditsRead

logger = logging.getLogger(__name__)

Action = Literal["ai_answer", "deep_check", "resume_assistant"]

CREDITS_PER_MONTH = {"free": 30, "pro": 400}
COSTS: dict[Action, int] = {"ai_answer": 1, "deep_check": 2, "resume_assistant": 1}

_WHAT = {
    "ai_answer": "AI answer",
    "deep_check": "deep AI job check",
    "resume_assistant": "resume assistant message",
}


def period_of(moment: datetime) -> date:
    return date(moment.year, moment.month, 1)


def _next_period(period: date) -> datetime:
    if period.month == 12:
        return datetime(period.year + 1, 1, 1, tzinfo=UTC)
    return datetime(period.year, period.month + 1, 1, tzinfo=UTC)


def _day(moment: datetime) -> str:
    return f"{moment.day} {moment:%b}"


async def usage(db: AsyncSession, *, user_id: uuid.UUID) -> CreditsRead:
    now = datetime.now(UTC)
    period = period_of(now)
    plan: Literal["free", "pro"] = "pro" if await is_pro(db, user_id=user_id) else "free"
    limit = CREDITS_PER_MONTH[plan]
    used = await repository.used_in(db, user_id, period)
    return CreditsRead(
        plan=plan,
        used=used,
        limit=limit,
        left=max(0, limit - used),
        resets_at=_next_period(period),
        pro_limit=CREDITS_PER_MONTH["pro"],
        costs={str(action): cost for action, cost in COSTS.items()},
    )


@dataclass(frozen=True)
class Balance:
    left: int
    limit: int


async def spend(db: AsyncSession, *, user_id: uuid.UUID, action: Action) -> Balance:
    """Takes the action's credits, or raises PlanLimitError."""
    now = datetime.now(UTC)
    period = period_of(now)
    pro = await is_pro(db, user_id=user_id)
    limit = CREDITS_PER_MONTH["pro" if pro else "free"]
    cost = COSTS[action]
    used = await repository.try_spend(db, user_id, period, cost, limit)
    if used is None:
        resets = _day(_next_period(period))
        if pro:
            message = (
                f"You have used this month's {limit} AI credits. They come back on {resets}."
                " Everything that does not use AI keeps working."
            )
        else:
            message = (
                f"You have used this month's {limit} free AI credits (a {_WHAT[action]} uses"
                f" {cost}). They come back on {resets}, or upgrade to Pro for"
                f" {CREDITS_PER_MONTH['pro']} a month in Settings."
            )
        raise PlanLimitError(message)
    return Balance(left=limit - used, limit=limit)


async def give_back(
    db: AsyncSession, *, user_id: uuid.UUID, action: Action, spent_at: datetime
) -> None:
    """Returns credits spent on work that then failed, to the month they came from.
    The caller commits."""
    await repository.give_back(db, user_id, period_of(spent_at), COSTS[action])
    logger.info("Gave back %s credits to %s for a failed %s", COSTS[action], user_id, action)
