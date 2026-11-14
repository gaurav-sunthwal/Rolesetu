"""The Razorpay calls Rolesetu makes, and the two signature checks.

Called with httpx rather than Razorpay's SDK: the SDK is synchronous (it would
block the event loop for every user during a payment call), and three endpoints
do not need it. Every call has a timeout; only reads are retried, because a
retried write could create a second order.
"""

import asyncio
import contextlib
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.core.config import get_settings
from backend.core.exceptions import UnavailableError

logger = logging.getLogger(__name__)

BASE_URL = "https://api.razorpay.com/v1"

_UNAVAILABLE = "Payments are not available right now. Nothing was charged. Please try again soon."


class RazorpayError(Exception):
    """Razorpay answered, but not with what was asked for."""


@dataclass(frozen=True)
class Keys:
    key_id: str
    key_secret: str


def keys() -> Keys | None:
    settings = get_settings()
    if settings.razorpay_key_id and settings.razorpay_key_secret:
        return Keys(settings.razorpay_key_id, settings.razorpay_key_secret)
    return None


def require_keys() -> Keys:
    found = keys()
    if found is None:
        raise UnavailableError(_UNAVAILABLE)
    return found


def _sign(message: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def payment_signature_ok(*, order_id: str, payment_id: str, signature: str, secret: str) -> bool:
    """The checkout's proof of payment: HMAC-SHA256 of "order_id|payment_id" with the
    key secret. Compared in constant time, so the check leaks nothing by its timing."""
    expected = _sign(f"{order_id}|{payment_id}".encode(), secret)
    return hmac.compare_digest(expected, signature)


def webhook_signature_ok(*, body: bytes, signature: str, secret: str) -> bool:
    """A webhook's proof it came from Razorpay: HMAC-SHA256 of the raw body, exactly
    as received (parsing and re-encoding it would change the bytes)."""
    return hmac.compare_digest(_sign(body, secret), signature)


# One client per process, kept open: a fresh connection to Razorpay costs a TLS
# handshake (measured 2.6s on the first call, 0.5s on a warm one).
_shared: tuple[str, httpx.AsyncClient] | None = None


def _client(found: Keys) -> httpx.AsyncClient:
    global _shared
    if _shared is None or _shared[0] != found.key_id or _shared[1].is_closed:
        client = httpx.AsyncClient(
            base_url=BASE_URL,
            auth=(found.key_id, found.key_secret),
            timeout=get_settings().razorpay_timeout_seconds,
            limits=httpx.Limits(max_keepalive_connections=5, keepalive_expiry=60),
        )
        _shared = (found.key_id, client)
    return _shared[1]


_WARM_FOR_SECONDS = 45.0
_warmed_at = 0.0
_warming: set["asyncio.Task[None]"] = set()


async def _ping(found: Keys) -> None:
    # Only a head start: the real call reports its own failure.
    with contextlib.suppress(httpx.HTTPError):
        await _client(found).get("/orders", params={"count": 1})


def warm_up() -> None:
    """Opens the connection in the background so the next payment call skips the
    handshake. At most once every 45s per process; never waits."""
    global _warmed_at
    found = keys()
    now = time.monotonic()
    if found is None or now - _warmed_at < _WARM_FOR_SECONDS:
        return
    _warmed_at = now
    task = asyncio.create_task(_ping(found))
    _warming.add(task)
    task.add_done_callback(_warming.discard)


async def close() -> None:
    """Closes the kept-open connection; called when the server stops."""
    global _shared
    if _shared is not None:
        await _shared[1].aclose()
        _shared = None


def _json(response: httpx.Response) -> dict[str, Any]:
    if response.status_code in (401, 403):
        # Our keys are wrong or revoked. The user did nothing wrong, so this is
        # reported as unavailable, never as their sign-in failing.
        logger.error("Razorpay refused Rolesetu's keys (%s)", response.status_code)
        raise UnavailableError(_UNAVAILABLE)
    if response.status_code >= 500:
        raise httpx.HTTPStatusError("Razorpay is down", request=response.request, response=response)
    if response.status_code >= 400:
        # Razorpay's message names fields and ids; it goes to the log, not to users.
        logger.warning("Razorpay said %s: %s", response.status_code, response.text[:500])
        raise RazorpayError(f"Razorpay answered {response.status_code}")
    data = response.json()
    if not isinstance(data, dict):
        raise RazorpayError("Razorpay answered with something other than an object")
    return data


async def create_order(
    *, amount: int, currency: str, receipt: str, notes: dict[str, str]
) -> dict[str, Any]:
    """A new order. Not retried: a lost answer is safer as an error the user retries
    (one unpaid order, which expires) than as two orders made behind their back."""
    found = require_keys()
    try:
        response = await _client(found).post(
            "/orders",
            json={"amount": amount, "currency": currency, "receipt": receipt, "notes": notes},
        )
        return _json(response)
    except (httpx.HTTPError, RazorpayError) as error:
        logger.warning("Could not create a Razorpay order: %s", error)
        raise UnavailableError(_UNAVAILABLE) from error


@retry(
    retry=retry_if_exception_type(httpx.HTTPError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    reraise=True,
)
async def _get(path: str) -> dict[str, Any]:
    return _json(await _client(require_keys()).get(path))


async def fetch_payment(payment_id: str) -> dict[str, Any]:
    """The payment as Razorpay has it: the only source trusted to say it was paid."""
    try:
        return await _get(f"/payments/{payment_id}")
    except (httpx.HTTPError, RazorpayError) as error:
        logger.warning("Could not read Razorpay payment %s: %s", payment_id, error)
        raise UnavailableError(
            "We could not confirm your payment with Razorpay just now. If you were charged,"
            " Pro turns on by itself within a few minutes; otherwise please try again."
        ) from error


async def capture_payment(payment_id: str, *, amount: int, currency: str) -> dict[str, Any]:
    """Takes an authorised payment. Only needed when the account does not capture
    automatically; Razorpay refuses a second capture, so this is safe to repeat."""
    found = require_keys()
    try:
        response = await _client(found).post(
            f"/payments/{payment_id}/capture", json={"amount": amount, "currency": currency}
        )
        return _json(response)
    except (httpx.HTTPError, RazorpayError):
        # Already captured, or a lost answer: read what really happened instead.
        return await fetch_payment(payment_id)


async def refund_payment(payment_id: str, *, amount: int, key: str) -> dict[str, Any]:
    """Sends the money back. Not retried: a lost answer is settled by reading the
    payment (`amount_refunded`), never by asking again. `key` is sent as Razorpay's
    refund idempotency key, so the same refund asked twice is made once."""
    found = require_keys()
    response = await _client(found).post(
        f"/payments/{payment_id}/refund",
        json={"amount": amount, "speed": "normal", "receipt": key[:40]},
        headers={"X-Refund-Idempotency": key},
    )
    return _json(response)


# --- Autopay (Razorpay Subscriptions) ---------------------------------------------


async def _post(path: str, body: dict[str, Any], what: str) -> dict[str, Any]:
    """A write. Not retried: a lost answer must not make a second plan, subscription
    or cancellation behind the user's back; the caller reads back what happened."""
    found = require_keys()
    try:
        return _json(await _client(found).post(path, json=body))
    except (httpx.HTTPError, RazorpayError) as error:
        logger.warning("Razorpay %s failed: %s", what, error)
        raise UnavailableError(_UNAVAILABLE) from error


async def create_plan(*, amount: int, currency: str, name: str, description: str) -> dict[str, Any]:
    """A monthly Razorpay plan at a fixed amount. One per price: a plan's amount can
    never change, so a new price needs a new plan."""
    return await _post(
        "/plans",
        {
            "period": "monthly",
            "interval": 1,
            "item": {
                "name": name,
                "amount": amount,
                "currency": currency,
                "description": description,
            },
            "notes": {"rolesetu_price": f"{currency}:{amount}"},
        },
        "plan creation",
    )


async def create_subscription(
    *,
    plan_id: str,
    total_count: int,
    notes: dict[str, str],
    start_at: int | None = None,
    offer_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "plan_id": plan_id,
        "total_count": total_count,
        "quantity": 1,
        "customer_notify": 1,
        "notes": notes,
    }
    if start_at is not None:
        body["start_at"] = start_at
    if offer_id:
        body["offer_id"] = offer_id
    return await _post("/subscriptions", body, "subscription creation")


async def fetch_subscription(subscription_id: str) -> dict[str, Any]:
    """The subscription as Razorpay has it: the only source trusted for its state."""
    try:
        return await _get(f"/subscriptions/{subscription_id}")
    except (httpx.HTTPError, RazorpayError) as error:
        logger.warning("Could not read Razorpay subscription %s: %s", subscription_id, error)
        raise UnavailableError(
            "We could not check your autopay with Razorpay just now. If you were charged,"
            " Pro turns on by itself within a few minutes; otherwise please try again."
        ) from error


async def fetch_invoice(invoice_id: str) -> dict[str, Any]:
    """Which subscription a charge was for: a payment names its invoice, and the
    invoice names its subscription."""
    try:
        return await _get(f"/invoices/{invoice_id}")
    except (httpx.HTTPError, RazorpayError) as error:
        logger.warning("Could not read Razorpay invoice %s: %s", invoice_id, error)
        raise UnavailableError(_UNAVAILABLE) from error


async def cancel_subscription(subscription_id: str, *, at_cycle_end: bool) -> dict[str, Any]:
    """Stops future charges. `at_cycle_end` keeps the month already paid for running.
    Asking to cancel a cancelled subscription fails, so on any failure the
    subscription is read back and returned as it is."""
    found = require_keys()
    try:
        return _json(
            await _client(found).post(
                f"/subscriptions/{subscription_id}/cancel",
                json={"cancel_at_cycle_end": 1 if at_cycle_end else 0},
            )
        )
    except (httpx.HTTPError, RazorpayError) as error:
        logger.warning(
            "Cancelling subscription %s did not answer cleanly: %s", subscription_id, error
        )
        return await fetch_subscription(subscription_id)


def subscription_signature_ok(
    *, payment_id: str, subscription_id: str, signature: str, secret: str
) -> bool:
    """The checkout's proof for an autopay mandate: HMAC-SHA256 of
    "payment_id|subscription_id" with the key secret, compared in constant time."""
    expected = _sign(f"{payment_id}|{subscription_id}".encode(), secret)
    return hmac.compare_digest(expected, signature)
