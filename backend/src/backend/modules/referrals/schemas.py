from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ReferralClaim(BaseModel):
    code: str = Field(min_length=6, max_length=12, pattern=r"^[A-Za-z0-9]+$")


class ReferredFriend(BaseModel):
    """A friend who joined. Nothing about them beyond where they are: their own
    data (resume, checks) stays theirs."""

    joined_at: datetime
    status: Literal["joined", "unlocked", "used"]


class ReferralSummary(BaseModel):
    code: str
    friends: list[ReferredFriend]
    rewards_available: int = Field(description="Months that can be bought at the referral price.")
    referral_amount: int = Field(description="The referral price, in paise.")
    currency: str
    checks_needed: int = Field(description="Job checks a friend makes to unlock a reward.")
