"""What the admin panel reads and sends about payments, plans and Pro."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

OrderStatus = Literal["created", "paid", "refunded", "revoked"]


class PlanAdminRead(BaseModel):
    plan: str
    description: str
    amount: int = Field(description="In the currency's smallest unit (paise for INR).")
    currency: str
    days: int
    active: bool
    updated_by: str | None
    updated_at: datetime | None


class PlanWrite(BaseModel):
    description: str = Field(min_length=3, max_length=120)
    # At least ₹1 (Razorpay's minimum), at most ₹1,00,000.
    amount: int = Field(ge=100, le=10_000_000)
    days: int = Field(ge=1, le=366)
    active: bool
    note: str | None = Field(None, max_length=200)


class OrderAdminRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    plan: str
    kind: Literal["payment", "grant"]
    amount: int
    currency: str
    status: OrderStatus
    razorpay_order_id: str | None
    razorpay_payment_id: str | None
    created_at: datetime
    paid_at: datetime | None
    pro_starts_at: datetime | None
    pro_ends_at: datetime | None
    refunded_at: datetime | None
    refund_id: str | None
    note: str | None
    # The payment in Razorpay's dashboard, for anything done by hand there.
    razorpay_url: str | None


class BillingActionRead(BaseModel):
    id: uuid.UUID
    created_at: datetime
    action: str
    admin_email: str
    user_id: uuid.UUID | None
    user_email: str | None
    order_id: uuid.UUID | None
    note: str | None
    amount: int | None
    days: int | None


class BillingOverview(BaseModel):
    payments_enabled: bool
    webhook_enabled: bool
    plans: list[PlanAdminRead]
    # People with Pro right now: paid for, or given by an admin.
    pro_now: int
    paying_now: int
    granted_now: int
    # Pro ends in the next 7 days and nothing is bought after it.
    expiring_7d: int
    currency: str
    revenue_30d: int
    revenue_total: int
    refunded_total: int
    orders_30d: int
    paid_30d: int
    recent_actions: list[BillingActionRead]


class UserBillingAdmin(BaseModel):
    plan: Literal["free", "pro"]
    pro_until: datetime | None
    orders: list[OrderAdminRead]
    actions: list[BillingActionRead]


class GrantWrite(BaseModel):
    days: int = Field(ge=1, le=366)
    note: str = Field(min_length=3, max_length=200)


class NoteWrite(BaseModel):
    note: str = Field(min_length=3, max_length=200)
