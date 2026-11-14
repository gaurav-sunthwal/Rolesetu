"""Buying Pro with Razorpay: the signature checks, and every way a payment could be
faked, reused or misread, through the API and database. Razorpay itself is
replaced by a fake that never touches money.

The API tests are skipped until migration c3e5a7b9d2f4 has been applied to the
database the tests use.
"""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text

from backend.core.config import get_settings
from backend.db.session import get_sessionmaker
from backend.modules.billing import razorpay
from backend.tests.conftest import ClientFactory

API = "/api/v1"
SECRET = "test-key-secret"
WEBHOOK_SECRET = "test-webhook-secret"
# Kept before any test swaps it for the fake.
REAL_CREATE_ORDER = razorpay.create_order


def sign(order_id: str, payment_id: str, secret: str = SECRET) -> str:
    return hmac.new(
        secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()


def sign_body(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# --- Signatures (no database) ---------------------------------------------------


def test_payment_signature_matches_only_the_exact_order_and_payment() -> None:
    good = sign("order_A", "pay_B")
    assert razorpay.payment_signature_ok(
        order_id="order_A", payment_id="pay_B", signature=good, secret=SECRET
    )
    assert not razorpay.payment_signature_ok(
        order_id="order_A", payment_id="pay_C", signature=good, secret=SECRET
    )
    assert not razorpay.payment_signature_ok(
        order_id="order_X", payment_id="pay_B", signature=good, secret=SECRET
    )
    assert not razorpay.payment_signature_ok(
        order_id="order_A", payment_id="pay_B", signature=good, secret="other-secret"
    )


def test_webhook_signature_covers_the_raw_body() -> None:
    body = b'{"event":"order.paid"}'
    assert razorpay.webhook_signature_ok(
        body=body, signature=sign_body(body), secret=WEBHOOK_SECRET
    )
    assert not razorpay.webhook_signature_ok(
        body=b'{"event": "order.paid"}', signature=sign_body(body), secret=WEBHOOK_SECRET
    )


# --- Through the API --------------------------------------------------------------


class FakeRazorpay:
    """Orders and payments as Razorpay would hold them."""

    def __init__(self) -> None:
        self.orders: dict[str, dict[str, Any]] = {}
        self.payments: dict[str, dict[str, Any]] = {}
        self.captures = 0

    async def create_order(
        self, *, amount: int, currency: str, receipt: str, notes: dict[str, str]
    ) -> dict[str, Any]:
        order_id = f"order_{uuid.uuid4().hex[:14]}"
        order: dict[str, Any] = {"id": order_id, "amount": amount, "currency": currency}
        self.orders[order_id] = order
        return order

    def pay(self, order_id: str, *, status: str = "captured", **changes: Any) -> str:
        order = self.orders[order_id]
        payment_id = f"pay_{uuid.uuid4().hex[:14]}"
        self.payments[payment_id] = {
            "id": payment_id,
            "order_id": order_id,
            "amount": order["amount"],
            "currency": order["currency"],
            "status": status,
        } | changes
        return payment_id

    async def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        return dict(self.payments[payment_id])

    async def capture_payment(
        self, payment_id: str, *, amount: int, currency: str
    ) -> dict[str, Any]:
        self.captures += 1
        self.payments[payment_id]["status"] = "captured"
        return dict(self.payments[payment_id])


def install_fake_razorpay(monkeypatch: pytest.MonkeyPatch) -> FakeRazorpay:
    """Swaps every Razorpay call for the fake. Shared with other billing tests."""
    fake = FakeRazorpay()
    monkeypatch.setattr(razorpay, "keys", lambda: razorpay.Keys("rzp_test_fake", SECRET))
    monkeypatch.setattr(razorpay, "create_order", fake.create_order)
    monkeypatch.setattr(razorpay, "fetch_payment", fake.fetch_payment)
    monkeypatch.setattr(razorpay, "capture_payment", fake.capture_payment)
    monkeypatch.setattr(razorpay, "warm_up", lambda: None)
    monkeypatch.setattr(get_settings(), "razorpay_webhook_secret", WEBHOOK_SECRET)
    return fake


@pytest.fixture
async def fake(monkeypatch: pytest.MonkeyPatch) -> FakeRazorpay:
    async with get_sessionmaker()() as db:
        found = await db.execute(text("select to_regclass('public.billing_orders')"))
        if found.scalar_one() is None:
            pytest.skip("Apply migration c3e5a7b9d2f4 to run these tests.")
    return install_fake_razorpay(monkeypatch)


async def start(client: AsyncClient, body: dict[str, Any] | None = None) -> dict[str, Any]:
    response = await client.post(f"{API}/billing/orders", json=body or {"plan": "pro_month"})
    assert response.status_code == 200, response.text
    return dict(response.json())


async def verify(
    client: AsyncClient, order_id: str, payment_id: str, signature: str | None = None
) -> Response:
    return await client.post(
        f"{API}/billing/orders/verify",
        json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature or sign(order_id, payment_id),
        },
    )


async def plan_of(client: AsyncClient) -> dict[str, Any]:
    response = await client.get(f"{API}/billing/me")
    assert response.status_code == 200
    return dict(response.json())


async def test_new_user_is_free_and_sees_the_price(client: AsyncClient, fake: FakeRazorpay) -> None:
    plan = await plan_of(client)
    assert plan["plan"] == "free"
    assert plan["pro_until"] is None
    assert plan["payments_enabled"] is True
    assert plan["price"] == {"plan": "pro_month", "amount": 19900, "currency": "INR", "days": 30}


async def test_the_price_comes_from_the_server_not_the_request(
    client: AsyncClient, fake: FakeRazorpay
) -> None:
    order = await start(client, {"plan": "pro_month", "amount": 100, "currency": "USD"})
    assert (order["amount"], order["currency"]) == (19900, "INR")
    assert fake.orders[order["order_id"]]["amount"] == 19900
    assert order["key_id"] == "rzp_test_fake"
    assert SECRET not in json.dumps(order)

    unknown = await client.post(f"{API}/billing/orders", json={"plan": "pro_forever"})
    assert unknown.status_code == 422


async def test_a_confirmed_payment_gives_one_month_of_pro(
    client: AsyncClient, fake: FakeRazorpay
) -> None:
    order = await start(client)
    payment_id = fake.pay(order["order_id"])

    response = await verify(client, order["order_id"], payment_id)
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["plan"] == "pro"
    until = datetime.fromisoformat(plan["pro_until"])
    assert abs(until - (datetime.now(UTC) + timedelta(days=30))) < timedelta(minutes=1)
    assert len(plan["payments"]) == 1

    # The checkout's callback can arrive twice; the second changes nothing.
    again = await verify(client, order["order_id"], payment_id)
    assert again.status_code == 200
    assert again.json()["pro_until"] == plan["pro_until"]
    assert len(again.json()["payments"]) == 1


async def test_a_forged_signature_is_refused(client: AsyncClient, fake: FakeRazorpay) -> None:
    order = await start(client)
    payment_id = fake.pay(order["order_id"])

    forged = await verify(client, order["order_id"], payment_id, sign("x", "y"))
    assert forged.status_code == 400
    wrong_secret = await verify(
        client, order["order_id"], payment_id, sign(order["order_id"], payment_id, "guess")
    )
    assert wrong_secret.status_code == 400
    assert (await plan_of(client))["plan"] == "free"


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "failed"},
        {"status": "created"},
        {"status": "refunded"},
        {"amount": 100},
        {"currency": "USD"},
    ],
)
async def test_a_payment_razorpay_does_not_confirm_in_full_gives_nothing(
    client: AsyncClient, fake: FakeRazorpay, changes: dict[str, Any]
) -> None:
    order = await start(client)
    payment_id = fake.pay(order["order_id"], **changes)
    response = await verify(client, order["order_id"], payment_id)
    assert response.status_code == 400
    assert (await plan_of(client))["plan"] == "free"


async def test_a_payment_for_another_order_cannot_pay_this_one(
    client: AsyncClient, fake: FakeRazorpay
) -> None:
    cheap = await start(client)
    other = await fake.create_order(amount=19900, currency="INR", receipt="x", notes={})
    payment_id = fake.pay(other["id"])
    # Signed correctly for the pair sent, but Razorpay says it paid a different order.
    response = await verify(client, cheap["order_id"], payment_id)
    assert response.status_code == 400
    assert (await plan_of(client))["plan"] == "free"


async def test_one_user_cannot_use_another_users_order(
    make_client: ClientFactory, fake: FakeRazorpay
) -> None:
    owner, other = make_client(), make_client()
    order = await start(owner)
    payment_id = fake.pay(order["order_id"])

    response = await verify(other, order["order_id"], payment_id)
    assert response.status_code == 404
    assert (await plan_of(other))["plan"] == "free"
    assert (await plan_of(owner))["plan"] == "free"


async def test_an_authorised_payment_is_captured_first(
    client: AsyncClient, fake: FakeRazorpay
) -> None:
    order = await start(client)
    payment_id = fake.pay(order["order_id"], status="authorized")
    response = await verify(client, order["order_id"], payment_id)
    assert response.status_code == 200
    assert fake.captures == 1
    assert response.json()["plan"] == "pro"


async def test_a_second_month_cannot_be_bought_by_mistake(
    client: AsyncClient, fake: FakeRazorpay
) -> None:
    order = await start(client)
    await verify(client, order["order_id"], fake.pay(order["order_id"]))

    again = await client.post(f"{API}/billing/orders", json={"plan": "pro_month"})
    assert again.status_code == 409
    assert "You already have Pro until" in again.json()["detail"]


@pytest.mark.parametrize("failure", ["keys refused", "server error", "no connection"])
async def test_razorpay_failing_is_never_a_sign_in_error(
    client: AsyncClient,
    fake: FakeRazorpay,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    """The real Razorpay client, against a network that fails the way Razorpay can."""

    def answer(request: httpx.Request) -> httpx.Response:
        if failure == "no connection":
            raise httpx.ConnectError("unreachable", request=request)
        status = 401 if failure == "keys refused" else 500
        return httpx.Response(status, json={"error": {"description": "internal"}})

    def failing_client(_: razorpay.Keys) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=razorpay.BASE_URL, transport=httpx.MockTransport(answer))

    monkeypatch.setattr(razorpay, "create_order", REAL_CREATE_ORDER)
    monkeypatch.setattr(razorpay, "_client", failing_client)

    response = await client.post(f"{API}/billing/orders", json={"plan": "pro_month"})
    assert response.status_code == 503
    assert "Nothing was charged" in response.json()["detail"]
    assert "internal" not in response.json()["detail"]  # Razorpay's words stay in the log
    assert (await plan_of(client))["plan"] == "free"


async def test_payments_are_off_without_keys(
    client: AsyncClient, fake: FakeRazorpay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(razorpay, "keys", lambda: None)
    assert (await plan_of(client))["payments_enabled"] is False
    response = await client.post(f"{API}/billing/orders", json={"plan": "pro_month"})
    assert response.status_code == 503


def webhook_body(order_id: str, payment_id: str, event: str = "order.paid") -> bytes:
    return json.dumps(
        {
            "event": event,
            "payload": {
                "payment": {"entity": {"id": payment_id, "order_id": order_id}},
                "order": {"entity": {"id": order_id}},
            },
        }
    ).encode()


async def post_webhook(client: AsyncClient, body: bytes, signature: str | None) -> Response:
    headers = {"content-type": "application/json"}
    if signature is not None:
        headers["x-razorpay-signature"] = signature
    return await client.post(f"{API}/billing/webhooks/razorpay", content=body, headers=headers)


async def test_the_webhook_gives_pro_when_the_browser_closed_first(
    client: AsyncClient, fake: FakeRazorpay
) -> None:
    order = await start(client)
    payment_id = fake.pay(order["order_id"])
    body = webhook_body(order["order_id"], payment_id)

    response = await post_webhook(client, body, sign_body(body))
    assert response.status_code == 200
    first = await plan_of(client)
    assert first["plan"] == "pro"

    # Razorpay retries webhooks, and the checkout may still call back: neither
    # adds a second month.
    assert (await post_webhook(client, body, sign_body(body))).status_code == 200
    assert (await verify(client, order["order_id"], payment_id)).status_code == 200
    after = await plan_of(client)
    assert after["pro_until"] == first["pro_until"]
    assert len(after["payments"]) == 1


async def test_an_unsigned_or_forged_webhook_does_nothing(
    client: AsyncClient, fake: FakeRazorpay
) -> None:
    order = await start(client)
    payment_id = fake.pay(order["order_id"])
    body = webhook_body(order["order_id"], payment_id)

    assert (await post_webhook(client, body, None)).status_code == 400
    assert (await post_webhook(client, body, sign_body(body, "guess"))).status_code == 400
    assert (await post_webhook(client, body, sign_body(b"other body"))).status_code == 400
    assert (await plan_of(client))["plan"] == "free"


async def test_a_signed_webhook_still_needs_razorpay_to_confirm_the_payment(
    client: AsyncClient, fake: FakeRazorpay
) -> None:
    order = await start(client)
    payment_id = fake.pay(order["order_id"], status="failed")
    body = webhook_body(order["order_id"], payment_id)
    assert (await post_webhook(client, body, sign_body(body))).status_code == 200
    assert (await plan_of(client))["plan"] == "free"


async def test_the_webhook_is_refused_until_its_secret_is_set(
    client: AsyncClient, fake: FakeRazorpay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "razorpay_webhook_secret", None)
    body = webhook_body("order_x", "pay_x")
    assert (await post_webhook(client, body, sign_body(body))).status_code == 503
