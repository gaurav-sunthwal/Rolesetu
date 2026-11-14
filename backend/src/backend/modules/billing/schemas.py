from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PriceRead(BaseModel):
    plan: str
    amount: int = Field(description="In the currency's smallest unit (paise for INR).")
    currency: str
    days: int


class PaymentRead(BaseModel):
    amount: int
    currency: str
    paid_at: datetime
    pro_starts_at: datetime
    pro_ends_at: datetime


class PlanRead(BaseModel):
    plan: Literal["free", "pro"]
    pro_until: datetime | None = Field(
        description="When the paid time ends, including months bought in advance."
    )
    renew_from: datetime | None = Field(
        description="From when the next month can be bought; None if it can be bought now."
    )
    payments_enabled: bool
    price: PriceRead = Field(description="What this user's next month costs.")
    referral_price: bool = Field(
        default=False, description="The price is lowered by a friend's referral reward."
    )
    payments: list[PaymentRead]


class OrderCreate(BaseModel):
    plan: Literal["pro_month"] = "pro_month"


class OrderRead(BaseModel):
    """Everything the Razorpay checkout needs. The key id is public by design."""

    order_id: str
    amount: int
    currency: str
    key_id: str
    name: str
    description: str
    email: str


class _WebhookPayment(BaseModel):
    id: str
    order_id: str | None = None


class _WebhookPaymentWrapper(BaseModel):
    entity: _WebhookPayment


class _WebhookPayload(BaseModel):
    payment: _WebhookPaymentWrapper | None = None


class WebhookEvent(BaseModel):
    """The few fields of a Razorpay webhook Rolesetu reads. The payment's state is
    not taken from here: it is asked of Razorpay again before anything is given."""

    event: str
    payload: _WebhookPayload


class PaymentVerify(BaseModel):
    razorpay_order_id: str = Field(pattern=r"^order_[A-Za-z0-9]{1,40}$")
    razorpay_payment_id: str = Field(pattern=r"^pay_[A-Za-z0-9]{1,40}$")
    razorpay_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
