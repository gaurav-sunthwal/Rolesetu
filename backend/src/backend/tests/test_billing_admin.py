"""The admin panel's control over payments and Pro: giving and removing months,
refunds through Razorpay (faked, never real money), price changes, and that only
admins can do any of it.

Price tests use a plan made up for the test, never the real one: these tests run
against a shared database, and the live price must not change while they run.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from backend.core.config import get_settings
from backend.db.session import get_sessionmaker
from backend.modules.billing import admin as billing_admin
from backend.modules.billing import prices, razorpay
from backend.modules.billing.models import BillingAdminAction, BillingOrder, BillingPlan
from backend.modules.billing.plans import Price
from backend.tests.conftest import ClientFactory
from backend.tests.test_billing import FakeRazorpay, plan_of, start, verify
from backend.tests.test_billing import fake as fake  # noqa: F401  (the fixture)

API = "/api/v1"
ADMIN = f"{API}/admin"
NOTE = {"note": "Support request #12"}


# ── Moving months up (no database) ────────────────────────────────────────────


def _row(starts: datetime, days: int) -> BillingOrder:
    return BillingOrder(
        id=uuid.uuid4(),
        status="paid",
        amount=19900,
        pro_starts_at=starts,
        pro_ends_at=starts + timedelta(days=days),
    )


def test_months_still_to_come_move_up_when_one_is_taken_away() -> None:
    now = datetime(2026, 11, 14, tzinfo=UTC)
    running = _row(now - timedelta(days=10), 30)  # ends in 20 days
    # A month that was due after a removed one, leaving a 30-day gap.
    later = _row(now + timedelta(days=50), 30)
    billing_admin.restack([later, running], now)
    assert running.pro_ends_at == now + timedelta(days=20)  # running months never move
    assert later.pro_starts_at == running.pro_ends_at
    assert later.pro_ends_at == running.pro_ends_at + timedelta(days=30)


def test_with_nothing_running_the_next_month_starts_now() -> None:
    now = datetime(2026, 11, 14, tzinfo=UTC)
    later = _row(now + timedelta(days=12), 30)
    billing_admin.restack([later], now)
    assert later.pro_starts_at == now and later.pro_ends_at == now + timedelta(days=30)


# ── Through the API (needs migration e5a7c9d1f3b6 applied) ────────────────────


class RefundingRazorpay(FakeRazorpay):
    def __init__(self) -> None:
        super().__init__()
        self.refunds: list[str] = []
        self.lose_answer = False
        self.refuse = False

    async def refund_payment(self, payment_id: str, *, amount: int, key: str) -> dict[str, Any]:
        if self.refuse:
            raise razorpay.RazorpayError("Razorpay answered 400")
        self.refunds.append(key)
        self.payments[payment_id]["amount_refunded"] = amount
        if self.lose_answer:
            raise httpx.ReadTimeout("lost")
        return {"id": f"rfnd_{uuid.uuid4().hex[:14]}", "amount": amount}


@pytest.fixture
async def rzp(fake: FakeRazorpay, monkeypatch: pytest.MonkeyPatch) -> RefundingRazorpay:
    refunding = RefundingRazorpay()
    monkeypatch.setattr(razorpay, "create_order", refunding.create_order)
    monkeypatch.setattr(razorpay, "fetch_payment", refunding.fetch_payment)
    monkeypatch.setattr(razorpay, "capture_payment", refunding.capture_payment)
    monkeypatch.setattr(razorpay, "refund_payment", refunding.refund_payment)
    return refunding


@pytest.fixture
async def admin(make_client: ClientFactory, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    client = make_client()
    client.headers["x-test-verified"] = "1"
    monkeypatch.setattr(
        get_settings(), "admin_emails", [f"{client.headers['x-test-uid']}@example.com"]
    )
    return client


async def user_id_of(client: AsyncClient) -> str:
    return str((await client.get(f"{API}/users/me")).json()["id"])


async def buy_month(client: AsyncClient, rzp: RefundingRazorpay) -> str:
    order = await start(client)
    payment_id = rzp.pay(order["order_id"])
    assert (await verify(client, order["order_id"], payment_id)).status_code == 200
    return str(order["order_id"])


async def orders_of(admin: AsyncClient, user_id: str) -> dict[str, Any]:
    response = await admin.get(f"{ADMIN}/users/{user_id}/billing")
    assert response.status_code == 200, response.text
    return dict(response.json())


def _days_from_now(moment: str, days: int) -> bool:
    expected = datetime.now(UTC) + timedelta(days=days)
    return abs(datetime.fromisoformat(moment) - expected) < timedelta(minutes=2)


async def test_a_given_month_is_pro_after_the_paid_time_and_is_not_a_payment(
    client: AsyncClient, admin: AsyncClient, rzp: RefundingRazorpay
) -> None:
    user_id = await user_id_of(client)
    await buy_month(client, rzp)
    given = await admin.post(
        f"{ADMIN}/users/{user_id}/billing/grant", json={"days": 14, "note": "Beta tester"}
    )
    assert given.status_code == 201, given.text
    assert given.json()["kind"] == "grant" and given.json()["amount"] == 0
    assert _days_from_now(given.json()["pro_ends_at"], 30 + 14)

    plan = await plan_of(client)
    assert plan["plan"] == "pro" and _days_from_now(plan["pro_until"], 44)
    assert len(plan["payments"]) == 1  # a gift is not shown as a payment of ₹0

    history = await orders_of(admin, user_id)
    assert [a["action"] for a in history["actions"]] == ["grant"]
    assert history["actions"][0]["note"] == "Beta tester"


async def test_a_refund_goes_through_razorpay_once_and_moves_later_months_up(
    client: AsyncClient, admin: AsyncClient, rzp: RefundingRazorpay
) -> None:
    user_id = await user_id_of(client)
    await buy_month(client, rzp)
    given = (
        await admin.post(f"{ADMIN}/users/{user_id}/billing/grant", json={"days": 10, **NOTE})
    ).json()
    paid = next(o for o in (await orders_of(admin, user_id))["orders"] if o["kind"] == "payment")

    refunded = await admin.post(f"{ADMIN}/billing/orders/{paid['id']}/refund", json=NOTE)
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["status"] == "refunded" and refunded.json()["refund_id"]
    # Pressed again: nothing more is refunded.
    again = await admin.post(f"{ADMIN}/billing/orders/{paid['id']}/refund", json=NOTE)
    assert again.status_code == 200 and len(rzp.refunds) == 1

    # The given month now starts today instead of after the refunded one.
    history = await orders_of(admin, user_id)
    moved = next(o for o in history["orders"] if o["id"] == given["id"])
    assert _days_from_now(moved["pro_starts_at"], 0) and _days_from_now(moved["pro_ends_at"], 10)
    assert (await plan_of(client))["payments"] == []


async def test_a_refund_whose_answer_was_lost_is_recorded_from_razorpay(
    client: AsyncClient, admin: AsyncClient, rzp: RefundingRazorpay
) -> None:
    user_id = await user_id_of(client)
    await buy_month(client, rzp)
    paid = (await orders_of(admin, user_id))["orders"][0]
    rzp.lose_answer = True
    refunded = await admin.post(f"{ADMIN}/billing/orders/{paid['id']}/refund", json=NOTE)
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["status"] == "refunded"
    assert (await plan_of(client))["plan"] == "free"


async def test_a_refund_razorpay_refuses_changes_nothing(
    client: AsyncClient, admin: AsyncClient, rzp: RefundingRazorpay
) -> None:
    user_id = await user_id_of(client)
    await buy_month(client, rzp)
    paid = (await orders_of(admin, user_id))["orders"][0]
    rzp.refuse = True
    refused = await admin.post(f"{ADMIN}/billing/orders/{paid['id']}/refund", json=NOTE)
    assert refused.status_code == 503
    assert (await plan_of(client))["plan"] == "pro"
    assert (await orders_of(admin, user_id))["actions"] == []


async def test_a_given_month_cannot_be_refunded_but_can_be_removed(
    client: AsyncClient, admin: AsyncClient, rzp: RefundingRazorpay
) -> None:
    user_id = await user_id_of(client)
    given = (
        await admin.post(f"{ADMIN}/users/{user_id}/billing/grant", json={"days": 7, **NOTE})
    ).json()
    refund = await admin.post(f"{ADMIN}/billing/orders/{given['id']}/refund", json=NOTE)
    assert refund.status_code == 409
    removed = await admin.post(f"{ADMIN}/billing/orders/{given['id']}/revoke", json=NOTE)
    assert removed.status_code == 200 and removed.json()["status"] == "revoked"
    assert (await plan_of(client))["plan"] == "free"


async def test_ending_pro_removes_every_running_and_upcoming_month(
    client: AsyncClient, admin: AsyncClient, rzp: RefundingRazorpay
) -> None:
    user_id = await user_id_of(client)
    await buy_month(client, rzp)
    await admin.post(f"{ADMIN}/users/{user_id}/billing/grant", json={"days": 30, **NOTE})

    ended = await admin.post(f"{ADMIN}/users/{user_id}/billing/end", json=NOTE)
    assert ended.status_code == 200, ended.text
    assert ended.json()["plan"] == "free"
    assert {o["status"] for o in ended.json()["orders"]} == {"revoked"}
    assert rzp.refunds == []  # ending Pro never refunds by itself
    again = await admin.post(f"{ADMIN}/users/{user_id}/billing/end", json=NOTE)
    assert again.status_code == 409


async def test_the_overview_and_order_list_show_payments_and_gifts(
    client: AsyncClient, admin: AsyncClient, rzp: RefundingRazorpay
) -> None:
    user_id = await user_id_of(client)
    await buy_month(client, rzp)
    await admin.post(f"{ADMIN}/users/{user_id}/billing/grant", json={"days": 3, **NOTE})

    overview = (await admin.get(f"{ADMIN}/billing")).json()
    assert overview["pro_now"] >= 1 and overview["paying_now"] >= 1
    assert overview["revenue_30d"] >= 19900
    assert any(plan["plan"] == "pro_month" for plan in overview["plans"])

    grants = (await admin.get(f"{ADMIN}/billing/orders", params={"kind": "grant"})).json()
    assert all(order["kind"] == "grant" for order in grants["items"])
    assert any(order["user_id"] == user_id for order in grants["items"])
    page = (await admin.get(f"{ADMIN}/billing/orders", params={"limit": 1})).json()
    assert len(page["items"]) == 1 and page["next_cursor"]


@pytest.fixture
async def test_plan(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[str]:
    """A plan that exists only for this test."""
    plan = f"test_{uuid.uuid4().hex[:8]}"
    monkeypatch.setitem(
        prices.DEFAULTS,
        plan,
        Price(plan=plan, amount=19900, currency="INR", days=30, description="Test plan"),
    )
    yield plan
    async with get_sessionmaker()() as db:
        await db.execute(delete(BillingAdminAction).where(BillingAdminAction.note == plan))
        await db.execute(delete(BillingPlan).where(BillingPlan.plan == plan))
        await db.commit()


async def test_a_price_change_applies_from_the_next_order(
    admin: AsyncClient, rzp: RefundingRazorpay, test_plan: str
) -> None:
    body = {"description": "Pro, launch price", "amount": 14900, "days": 31, "active": True}
    changed = await admin.put(
        f"{ADMIN}/billing/plans/{test_plan}", json={**body, "note": test_plan}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["amount"] == 14900 and changed.json()["updated_by"]

    async with get_sessionmaker()() as db:
        price, on_sale = await prices.current_price(db, test_plan)
    assert (price.amount, price.days, on_sale) == (14900, 31, True)

    off = {**body, "active": False, "note": test_plan}
    assert (await admin.put(f"{ADMIN}/billing/plans/{test_plan}", json=off)).status_code == 200
    async with get_sessionmaker()() as db:
        assert (await prices.current_price(db, test_plan))[1] is False

    too_cheap = {**body, "amount": 50}
    assert (
        await admin.put(f"{ADMIN}/billing/plans/{test_plan}", json=too_cheap)
    ).status_code == 422
    unknown = await admin.put(f"{ADMIN}/billing/plans/pro_forever", json=body)
    assert unknown.status_code == 404


async def test_a_plan_taken_off_sale_cannot_be_bought(
    client: AsyncClient, rzp: RefundingRazorpay, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def off_sale(db: object, plan: str) -> tuple[Price, bool]:
        return prices.DEFAULTS[plan], False

    monkeypatch.setattr(prices, "current_price", off_sale)
    refused = await client.post(f"{API}/billing/orders", json={"plan": "pro_month"})
    assert refused.status_code == 503
    assert rzp.orders == {}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/billing"),
        ("GET", "/billing/orders"),
        ("PUT", "/billing/plans/pro_month"),
        ("POST", f"/billing/orders/{uuid.uuid4()}/refund"),
        ("POST", f"/billing/orders/{uuid.uuid4()}/revoke"),
        ("GET", f"/users/{uuid.uuid4()}/billing"),
        ("POST", f"/users/{uuid.uuid4()}/billing/grant"),
        ("POST", f"/users/{uuid.uuid4()}/billing/end"),
    ],
)
async def test_only_admins_can_touch_payments(client: AsyncClient, method: str, path: str) -> None:
    body = {"description": "x" * 5, "amount": 100, "days": 1, "active": True, "note": "abc"}
    response = await client.request(method, f"{ADMIN}{path}", json=body | {"days": 1})
    assert response.status_code == 403
