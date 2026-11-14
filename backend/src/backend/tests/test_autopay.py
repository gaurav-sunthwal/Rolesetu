"""Autopay (Razorpay Subscriptions), the payment funnel and payment reminder emails,
through the API and database. Razorpay is a fake that keeps plans, subscriptions,
invoices and payments the way Razorpay does; no money moves."""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text

from backend.core.config import get_settings
from backend.db.session import get_sessionmaker
from backend.modules.billing import razorpay, reminders
from backend.tests.conftest import ClientFactory
from backend.tests.test_billing import (
    API,
    SECRET,
    WEBHOOK_SECRET,
    FakeRazorpay,
    install_fake_razorpay,
    sign,
)

MONTH = 30 * 86400


def sign_sub(payment_id: str, subscription_id: str) -> str:
    return hmac.new(
        SECRET.encode(), f"{payment_id}|{subscription_id}".encode(), hashlib.sha256
    ).hexdigest()


def sign_body(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


class FakeAutopay:
    def __init__(self, base: FakeRazorpay) -> None:
        self.base = base
        self.plans: dict[str, dict[str, Any]] = {}
        self.subs: dict[str, dict[str, Any]] = {}
        self.invoices: dict[str, dict[str, Any]] = {}
        self.cancelled: list[tuple[str, bool]] = []
        self.created: list[dict[str, Any]] = []

    async def create_plan(
        self, *, amount: int, currency: str, name: str, description: str
    ) -> dict[str, Any]:
        plan_id = f"plan_{uuid.uuid4().hex[:14]}"
        self.plans[plan_id] = {"id": plan_id, "amount": amount, "currency": currency}
        return self.plans[plan_id]

    async def create_subscription(self, **kwargs: Any) -> dict[str, Any]:
        self.created.append(kwargs)
        sub_id = f"sub_{uuid.uuid4().hex[:14]}"
        self.subs[sub_id] = {
            "id": sub_id,
            "status": "created",
            "plan_id": kwargs["plan_id"],
            "start_at": kwargs.get("start_at"),
        }
        return dict(self.subs[sub_id])

    async def fetch_subscription(self, subscription_id: str) -> dict[str, Any]:
        return dict(self.subs[subscription_id])

    async def cancel_subscription(
        self, subscription_id: str, *, at_cycle_end: bool
    ) -> dict[str, Any]:
        self.cancelled.append((subscription_id, at_cycle_end))
        if not at_cycle_end:
            self.subs[subscription_id]["status"] = "cancelled"
        return dict(self.subs[subscription_id])

    async def fetch_invoice(self, invoice_id: str) -> dict[str, Any]:
        return dict(self.invoices[invoice_id])

    def charge(self, sub_id: str, *, amount: int = 19900, for_sub: str | None = None) -> str:
        """Razorpay charging a month: the subscription moves on, a payment is captured."""
        now = int(datetime.now(UTC).timestamp())
        sub = self.subs[sub_id]
        start = sub.get("current_end") or now
        sub.update(
            status="active", current_start=start, current_end=start + MONTH, charge_at=start + MONTH
        )
        invoice_id = f"inv_{uuid.uuid4().hex[:14]}"
        self.invoices[invoice_id] = {"id": invoice_id, "subscription_id": for_sub or sub_id}
        payment_id = f"pay_{uuid.uuid4().hex[:14]}"
        self.base.payments[payment_id] = {
            "id": payment_id,
            "order_id": f"order_{uuid.uuid4().hex[:14]}",
            "amount": amount,
            "currency": "INR",
            "status": "captured",
            "invoice_id": invoice_id,
        }
        return payment_id


@pytest.fixture
async def autopay(monkeypatch: pytest.MonkeyPatch) -> FakeAutopay:
    async with get_sessionmaker()() as db:
        found = await db.execute(text("select to_regclass('public.billing_subscriptions')"))
        if found.scalar_one() is None:
            pytest.skip("Apply migration b3d5f7a9c1e2 to run these tests.")
    fake = FakeAutopay(install_fake_razorpay(monkeypatch))
    for name in (
        "create_plan",
        "create_subscription",
        "fetch_subscription",
        "cancel_subscription",
        "fetch_invoice",
    ):
        monkeypatch.setattr(razorpay, name, getattr(fake, name))
    return fake


async def start(client: AsyncClient) -> dict[str, Any]:
    response = await client.post(f"{API}/billing/subscriptions", json={})
    assert response.status_code == 200, response.text
    return dict(response.json())


async def verify(
    client: AsyncClient, sub_id: str, payment_id: str, signature: str | None = None
) -> Response:
    return await client.post(
        f"{API}/billing/subscriptions/verify",
        json={
            "razorpay_subscription_id": sub_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature or sign_sub(payment_id, sub_id),
        },
    )


async def plan_of(client: AsyncClient) -> dict[str, Any]:
    return dict((await client.get(f"{API}/billing/me")).json())


async def webhook(client: AsyncClient, event: str, sub_id: str, payment_id: str | None) -> Response:
    payload: dict[str, Any] = {"subscription": {"entity": {"id": sub_id}}}
    if payment_id:
        payload["payment"] = {"entity": {"id": payment_id}}
    body = json.dumps({"event": event, "payload": payload}).encode()
    return await client.post(
        f"{API}/billing/webhooks/razorpay",
        content=body,
        headers={"content-type": "application/json", "x-razorpay-signature": sign_body(body)},
    )


async def test_autopay_turns_on_pro_and_each_charge_is_one_month(
    client: AsyncClient, autopay: FakeAutopay
) -> None:
    checkout = await start(client)
    assert checkout["amount"] == 19900 and checkout["first_amount"] == 19900
    assert checkout["starts_at"] is None and checkout["key_id"] == "rzp_test_fake"
    sub_id = checkout["subscription_id"]

    first = autopay.charge(sub_id)
    assert (await verify(client, sub_id, first)).status_code == 200
    plan = await plan_of(client)
    assert plan["plan"] == "pro" and len(plan["payments"]) == 1
    assert plan["autopay"]["on"] is True and plan["autopay"]["amount"] == 19900

    # The checkout and the webhook both report the first charge: recorded once.
    assert (await webhook(client, "subscription.charged", sub_id, first)).status_code == 200
    assert len((await plan_of(client))["payments"]) == 1

    # Next month, Razorpay charges again and says so by webhook.
    second = autopay.charge(sub_id)
    assert (await webhook(client, "subscription.charged", sub_id, second)).status_code == 200
    assert (await webhook(client, "subscription.charged", sub_id, second)).status_code == 200
    assert len((await plan_of(client))["payments"]) == 2


async def test_a_charge_for_another_subscription_is_not_counted(
    client: AsyncClient, autopay: FakeAutopay
) -> None:
    sub_id = (await start(client))["subscription_id"]
    stranger = autopay.charge(sub_id, for_sub="sub_someoneelse12")
    assert (await webhook(client, "subscription.charged", sub_id, stranger)).status_code == 200
    assert (await plan_of(client))["plan"] == "free"


async def test_a_forged_or_foreign_approval_is_refused(
    make_client: ClientFactory, autopay: FakeAutopay
) -> None:
    owner, other = make_client(), make_client()
    sub_id = (await start(owner))["subscription_id"]
    payment = autopay.charge(sub_id)
    assert (await verify(owner, sub_id, payment, sign("x", "y"))).status_code == 400
    assert (await verify(other, sub_id, payment)).status_code == 404
    assert (await plan_of(owner))["plan"] == "free"
    assert (await plan_of(other))["plan"] == "free"


async def test_one_autopay_at_a_time_and_no_one_time_payment_on_top(
    client: AsyncClient, autopay: FakeAutopay
) -> None:
    sub_id = (await start(client))["subscription_id"]
    # Not approved yet: asking again reuses the same mandate.
    assert (await start(client))["subscription_id"] == sub_id
    await verify(client, sub_id, autopay.charge(sub_id))
    again = await client.post(f"{API}/billing/subscriptions", json={})
    assert again.status_code == 409
    one_time = await client.post(f"{API}/billing/orders", json={"plan": "pro_month"})
    assert one_time.status_code == 409
    assert "Autopay is on" in one_time.json()["detail"]


async def test_someone_already_on_pro_starts_when_their_month_ends(
    client: AsyncClient, autopay: FakeAutopay
) -> None:
    order = (await client.post(f"{API}/billing/orders", json={"plan": "pro_month"})).json()
    paid = autopay.base.pay(order["order_id"])
    await client.post(
        f"{API}/billing/orders/verify",
        json={
            "razorpay_order_id": order["order_id"],
            "razorpay_payment_id": paid,
            "razorpay_signature": sign(order["order_id"], paid),
        },
    )
    until = datetime.fromisoformat((await plan_of(client))["pro_until"])
    await start(client)
    assert autopay.created[-1]["start_at"] == int(until.timestamp())


async def test_cancelling_keeps_the_paid_month(client: AsyncClient, autopay: FakeAutopay) -> None:
    sub_id = (await start(client))["subscription_id"]
    await verify(client, sub_id, autopay.charge(sub_id))
    response = await client.post(f"{API}/billing/subscriptions/cancel")
    assert response.status_code == 200
    plan = response.json()
    assert autopay.cancelled == [(sub_id, True)]
    assert plan["plan"] == "pro"
    assert plan["autopay"]["on"] is False and plan["autopay"]["cancel_at_cycle_end"] is True


async def test_a_referral_reward_makes_the_first_autopay_charge_149(
    make_client: ClientFactory, autopay: FakeAutopay, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.tests.test_referrals import claim, summary, use_rolesetu

    monkeypatch.setattr(get_settings(), "razorpay_referral_offer_id", "offer_test1234567890")
    owner, friend = make_client(), make_client()
    assert await claim(friend, (await summary(owner))["code"]) == 204
    await use_rolesetu(friend)

    checkout = await start(owner)
    assert checkout["first_amount"] == 14900 and checkout["amount"] == 19900
    assert autopay.created[-1]["offer_id"] == "offer_test1234567890"
    sub_id = checkout["subscription_id"]
    await verify(owner, sub_id, autopay.charge(sub_id, amount=14900))
    assert (await summary(owner))["rewards_available"] == 0


async def test_the_funnel_takes_known_steps_only(client: AsyncClient, autopay: FakeAutopay) -> None:
    ok = await client.post(
        f"{API}/billing/funnel",
        json={
            "step": "payment_failed",
            "detail": {"code": "BAD_REQUEST_ERROR", "reason": "card_declined"},
        },
    )
    assert ok.status_code == 204
    assert (await client.post(f"{API}/billing/funnel", json={"step": "hacked"})).status_code == 422
    bad_key = await client.post(
        f"{API}/billing/funnel", json={"step": "plan_viewed", "detail": {"Card Number": "4111"}}
    )
    assert bad_key.status_code == 422


async def test_someone_who_left_the_payment_window_gets_one_reminder(
    make_client: ClientFactory, autopay: FakeAutopay, monkeypatch: pytest.MonkeyPatch
) -> None:
    left, paid = make_client(), make_client()
    for client in (left, paid):
        await client.post(f"{API}/billing/funnel", json={"step": "checkout_opened"})
    sub_id = (await start(paid))["subscription_id"]
    await verify(paid, sub_id, autopay.charge(sub_id))

    sent: list[str] = []

    async def fake_send(**kwargs: Any) -> None:
        sent.append(kwargs["to"])

    monkeypatch.setattr(reminders, "send_email", fake_send)
    monkeypatch.setattr(reminders, "email_is_configured", lambda: True)
    later = datetime.now(UTC) + timedelta(hours=2)
    await reminders.send_due(later)
    left_email = f"{left.headers['x-test-uid']}@example.com"
    paid_email = f"{paid.headers['x-test-uid']}@example.com"
    assert left_email in sent and paid_email not in sent

    sent.clear()
    await reminders.send_due(later)  # a week must pass before another
    assert left_email not in sent


async def test_autopay_can_be_turned_back_on_after_cancelling(
    client: AsyncClient, autopay: FakeAutopay
) -> None:
    sub_id = (await start(client))["subscription_id"]
    await verify(client, sub_id, autopay.charge(sub_id))
    await client.post(f"{API}/billing/subscriptions/cancel")
    # The cancelled mandate keeps its paid month; a new one starts when it ends.
    again = await start(client)
    assert again["subscription_id"] != sub_id
    assert again["starts_at"] is not None
    assert (sub_id, False) not in autopay.cancelled


async def test_ending_pro_from_the_admin_panel_stops_autopay(
    make_client: ClientFactory, autopay: FakeAutopay, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, admin = make_client(), make_client()
    admin.headers["x-test-verified"] = "1"
    monkeypatch.setattr(
        get_settings(), "admin_emails", [f"{admin.headers['x-test-uid']}@example.com"]
    )
    sub_id = (await start(user))["subscription_id"]
    await verify(user, sub_id, autopay.charge(sub_id))
    user_id = (await user.get(f"{API}/users/me")).json()["id"]

    response = await admin.post(
        f"{API}/admin/users/{user_id}/billing/end", json={"note": "Asked to stop"}
    )
    assert response.status_code == 200, response.text
    assert (sub_id, False) in autopay.cancelled
    assert (await plan_of(user))["plan"] == "free"


async def test_the_admin_funnel_shows_who_left_and_why(
    make_client: ClientFactory, autopay: FakeAutopay, monkeypatch: pytest.MonkeyPatch
) -> None:
    left, admin = make_client(), make_client()
    admin.headers["x-test-verified"] = "1"
    monkeypatch.setattr(
        get_settings(), "admin_emails", [f"{admin.headers['x-test-uid']}@example.com"]
    )
    for step, detail in (
        ("upgrade_clicked", {}),
        ("checkout_opened", {}),
        ("payment_failed", {"description": "Your bank declined this payment"}),
        ("checkout_closed", {"after_failure": True}),
    ):
        await left.post(f"{API}/billing/funnel", json={"step": step, "detail": detail})

    body = (await admin.get(f"{API}/admin/billing/funnel", params={"days": 1})).json()
    left_id = (await left.get(f"{API}/users/me")).json()["id"]
    row = next(user for user in body["dropped"] if user["user_id"] == left_id)
    assert row["last_step"] == "checkout_closed"
    assert row["last_error"] == "Your bank declined this payment"
    assert any(f["reason"] == "Your bank declined this payment" for f in body["failures"])
    steps = {step["step"]: step["users"] for step in body["steps"]}
    assert steps["checkout_opened"] >= 1

    timeline = (await admin.get(f"{API}/admin/users/{left_id}/billing-funnel")).json()
    assert [event["step"] for event in timeline][:2] == ["checkout_closed", "payment_failed"]
    assert (await left.get(f"{API}/admin/billing/funnel")).status_code == 403
