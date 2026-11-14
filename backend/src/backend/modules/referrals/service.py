"""Bring a friend, pay less: each friend who joins through your link and really uses
Rolesetu makes one of your Pro months cost the referral price (₹149).

The rules, and the abuse each one closes:

- A person can be invited once, by one person, and only while their account is new
  (`CLAIM_WITHIN`): nobody can attach an old account, or switch who invited them.
- Nobody can use their own code.
- A friend counts only after real use: a resume on Rolesetu and `CHECKS_NEEDED` job
  checks. An empty throwaway account unlocks nothing.
- One reward pays for one month, at most one per order. The referrer sees only how
  far each friend has got, never who they are or what they did.
- A reward set aside for an order that is never paid is not lost: the next order
  takes it. It is spent only when that order is paid, and an admin refund of the
  order gives it back.
"""

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from backend.modules.billing.plans import REFERRAL_AMOUNT
from backend.modules.referrals import repository
from backend.modules.referrals.models import Referral
from backend.modules.referrals.schemas import ReferralSummary, ReferredFriend
from backend.modules.users.models import User

logger = logging.getLogger(__name__)

CHECKS_NEEDED = 3
CLAIM_WITHIN = timedelta(days=14)
# No 0/O or 1/I/L: codes are read aloud and typed from screenshots.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 8


def _new_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LENGTH))


async def code_for(db: AsyncSession, *, user_id: uuid.UUID) -> str:
    """The user's invite code, made the first time it is asked for."""
    existing = await repository.code_of(db, user_id)
    if existing:
        return existing
    for _ in range(5):  # a clash among 31^8 codes is rare; five tries is plenty
        saved = await repository.add_code(db, user_id, _new_code())
        if saved:
            return saved
        if existing := await repository.code_of(db, user_id):
            return existing  # made by a request running at the same time
    raise ConflictError("Could not make your invite link just now. Please try again.")


def _status(referral: Referral) -> str:
    if referral.used_at:
        return "used"
    return "unlocked" if referral.qualified_at else "joined"


async def summary(db: AsyncSession, *, user_id: uuid.UUID) -> ReferralSummary:
    code = await code_for(db, user_id=user_id)
    await repository.qualify(db, user_id, CHECKS_NEEDED)
    referrals = await repository.list_for_referrer(db, user_id)
    return ReferralSummary(
        code=code,
        friends=[
            ReferredFriend(joined_at=referral.created_at, status=_status(referral))  # type: ignore[arg-type]
            for referral in referrals
        ],
        rewards_available=sum(1 for r in referrals if r.qualified_at and not r.used_at),
        referral_amount=REFERRAL_AMOUNT,
        currency="INR",
        checks_needed=CHECKS_NEEDED,
    )


async def claim(db: AsyncSession, *, user: User, code: str) -> None:
    """Records that `user` joined through `code`. Asking again with the same code
    is fine; any other change is refused."""
    code = code.strip().upper()
    referrer_id = await repository.owner_of_code(db, code)
    if referrer_id is None:
        raise NotFoundError("That invite link is not valid.")
    if referrer_id == user.id:
        raise ValidationFailedError("You cannot use your own invite link.")
    existing = await repository.referral_of(db, user.id)
    if existing is not None:
        if existing.referrer_id == referrer_id:
            return
        raise ConflictError("You already joined through another invite.")
    if datetime.now(UTC) - user.created_at > CLAIM_WITHIN:
        raise ValidationFailedError("Invite links are for new accounts only.")
    if not await repository.add_referral(db, referrer_id, user.id):
        raise ConflictError("You already joined through another invite.")
    logger.info("User %s joined through %s's invite", user.id, referrer_id)


async def find_reward(db: AsyncSession, *, user_id: uuid.UUID) -> Referral | None:
    """An unlocked, unspent reward, locked until the transaction ends. Set it aside
    with `set_aside` once the order it pays for exists."""
    await repository.qualify(db, user_id, CHECKS_NEEDED)
    return await repository.first_reward(db, user_id)


def set_aside(reward: Referral, *, order_id: uuid.UUID) -> None:
    reward.order_id = order_id


async def has_reward(db: AsyncSession, *, user_id: uuid.UUID) -> bool:
    await repository.qualify(db, user_id, CHECKS_NEEDED)
    return any(
        r.qualified_at and not r.used_at for r in await repository.list_for_referrer(db, user_id)
    )


async def mark_used(db: AsyncSession, *, order_id: uuid.UUID) -> None:
    """The order was paid: its reward is spent."""
    await repository.mark_used(db, order_id, datetime.now(UTC))


async def spend(db: AsyncSession, *, referral_id: uuid.UUID, order_id: uuid.UUID) -> None:
    """An autopay's first charge was paid at the referral price: the reward it was
    made with is spent on that charge."""
    reward = await db.get(Referral, referral_id, with_for_update=True)
    if reward is not None and reward.used_at is None:
        reward.order_id = order_id
        reward.used_at = datetime.now(UTC)


async def release(db: AsyncSession, *, order_id: uuid.UUID) -> None:
    """The order was refunded: its reward can be used again."""
    await repository.release(db, order_id)
