"""What Rolesetu sells, in one place. The browser never sends a price: it asks for
a plan by name and the amount comes from here."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    plan: str
    # In the currency's smallest unit (paise for INR), as Razorpay takes it.
    amount: int
    currency: str
    days: int
    description: str


# One month of Pro, paid once (no autopay). Buying again adds a month after the
# current one ends, so paying early never loses days.
PRO_MONTH = Price(
    plan="pro_month", amount=19900, currency="INR", days=30, description="Rolesetu Pro, 1 month"
)

# How close to the end of a paid month the next one can be bought. Stops a second
# payment by mistake (two tabs, a double click) while still letting people renew.
RENEW_WITHIN_DAYS = 7

# What one month costs, in paise, when it is paid with a referral reward (a friend
# who joined through the user's link and really used Rolesetu). Never more than the
# price on sale: min() of the two is charged.
REFERRAL_AMOUNT = 14900
