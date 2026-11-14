"""The price of a plan right now: the admin panel's, else the default in plans.py.

Read on every order, so a price changed in the admin panel applies to the next
order at once on every API instance (nothing is cached in memory).
"""

from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.billing.models import BillingPlan
from backend.modules.billing.plans import PRO_MONTH, Price

# Plans people can buy, with what they cost before an admin first edits them.
DEFAULTS: dict[str, Price] = {PRO_MONTH.plan: PRO_MONTH}


async def current_price(db: AsyncSession, plan: str) -> tuple[Price, bool]:
    """The plan's price and whether it is on sale. Raises KeyError for a plan that
    does not exist."""
    default = DEFAULTS[plan]
    row = await db.get(BillingPlan, plan)
    if row is None:
        return default, True
    return (
        replace(
            default,
            amount=row.amount,
            currency=row.currency,
            days=row.days,
            description=row.description,
        ),
        row.active,
    )
