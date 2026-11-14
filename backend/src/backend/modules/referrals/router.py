from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.modules.referrals import service
from backend.modules.referrals.schemas import ReferralClaim, ReferralSummary
from backend.modules.users.dependencies import get_db_user
from backend.modules.users.models import User

router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.get("/me", response_model=ReferralSummary)
async def my_referrals(
    user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> ReferralSummary:
    """Your invite code, and how far each friend who joined has got."""
    return await service.summary(db, user_id=user.id)


@router.post("/claim", status_code=204)
async def claim_referral(
    payload: ReferralClaim, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)
) -> None:
    """Records the invite a new account signed up through."""
    await service.claim(db, user=user, code=payload.code)
