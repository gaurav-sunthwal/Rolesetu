import uuid
from datetime import datetime

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.referrals.models import Referral, ReferralCode


async def code_of(db: AsyncSession, user_id: uuid.UUID) -> str | None:
    result = await db.execute(select(ReferralCode.code).where(ReferralCode.user_id == user_id))
    return result.scalar_one_or_none()


async def add_code(db: AsyncSession, user_id: uuid.UUID, code: str) -> str | None:
    """Saves the code, or returns None if that code is taken. A user who already
    has one (two tabs at once) keeps theirs."""
    result = await db.execute(
        insert(ReferralCode)
        .values(user_id=user_id, code=code)
        .on_conflict_do_nothing()
        .returning(ReferralCode.code)
    )
    return result.scalar_one_or_none()


async def owner_of_code(db: AsyncSession, code: str) -> uuid.UUID | None:
    """Unscoped on purpose: an invite link names its owner to whoever opens it."""
    result = await db.execute(select(ReferralCode.user_id).where(ReferralCode.code == code))
    return result.scalar_one_or_none()


async def referral_of(db: AsyncSession, referred_id: uuid.UUID) -> Referral | None:
    result = await db.execute(select(Referral).where(Referral.referred_id == referred_id))
    return result.scalar_one_or_none()


async def add_referral(db: AsyncSession, referrer_id: uuid.UUID, referred_id: uuid.UUID) -> bool:
    """False when this person was already invited (by anyone)."""
    result = await db.execute(
        insert(Referral)
        .values(id=uuid.uuid4(), referrer_id=referrer_id, referred_id=referred_id)
        .on_conflict_do_nothing(index_elements=[Referral.referred_id])
        .returning(Referral.id)
    )
    return result.scalar_one_or_none() is not None


# A friend unlocks the reward once they have a resume on Rolesetu and have checked
# enough jobs: real use, which a throwaway account does not show.
_QUALIFY = text(
    """
    UPDATE referrals AS r SET qualified_at = now(), updated_at = now()
    WHERE r.referrer_id = :referrer_id
      AND r.qualified_at IS NULL
      AND EXISTS (SELECT 1 FROM resume_files f WHERE f.user_id = r.referred_id)
      AND (SELECT count(*) FROM matches m WHERE m.user_id = r.referred_id) >= :checks
    """
)


async def qualify(db: AsyncSession, referrer_id: uuid.UUID, checks: int) -> None:
    await db.execute(_QUALIFY, {"referrer_id": referrer_id, "checks": checks})


async def list_for_referrer(db: AsyncSession, referrer_id: uuid.UUID) -> list[Referral]:
    result = await db.execute(
        select(Referral)
        .where(Referral.referrer_id == referrer_id)
        .order_by(Referral.created_at.desc())
        .limit(100)
    )
    return list(result.scalars())


async def first_reward(db: AsyncSession, referrer_id: uuid.UUID) -> Referral | None:
    """The oldest unlocked, unspent reward. Locked so two orders made at once
    cannot both take it."""
    result = await db.execute(
        select(Referral)
        .where(
            Referral.referrer_id == referrer_id,
            Referral.qualified_at.is_not(None),
            Referral.used_at.is_(None),
        )
        .order_by(Referral.qualified_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return result.scalar_one_or_none()


async def mark_used(db: AsyncSession, order_id: uuid.UUID, when: datetime) -> None:
    await db.execute(
        update(Referral)
        .where(Referral.order_id == order_id, Referral.used_at.is_(None))
        .values(used_at=when)
    )


async def release(db: AsyncSession, order_id: uuid.UUID) -> None:
    await db.execute(
        update(Referral).where(Referral.order_id == order_id).values(used_at=None, order_id=None)
    )
