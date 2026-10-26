"""The email that tells us when someone signs in for the first time."""

import asyncio

import pytest

from backend.core.config import get_settings
from backend.modules.users import service as users_service
from backend.tests.conftest import ClientFactory

pytestmark = pytest.mark.signup_alerts

ALERT_TO = "alerts@example.com"


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    """The alerts these tests would have sent. Nothing really goes out."""
    outbox: list[dict[str, str]] = []

    async def record(**message: str) -> None:
        outbox.append(message)

    monkeypatch.setattr(users_service, "send_email", record)
    monkeypatch.setattr(get_settings(), "signup_alert_emails", [ALERT_TO])
    return outbox


async def test_a_first_sign_in_sends_one_alert(
    make_client: ClientFactory, sent: list[dict[str, str]]
) -> None:
    client = make_client()
    uid = client.headers["x-test-uid"]

    assert (await client.get("/api/v1/users/me")).status_code == 200
    assert (await client.get("/api/v1/users/me")).status_code == 200

    assert len(sent) == 1
    assert sent[0]["to"] == ALERT_TO
    assert f"{uid}@example.com" in sent[0]["subject"]
    assert "Accounts now" in sent[0]["text"]


async def test_the_first_burst_of_requests_alerts_once(
    make_client: ClientFactory, sent: list[dict[str, str]]
) -> None:
    """The dashboard fires several requests at once on a first sign-in."""
    client = make_client()

    responses = await asyncio.gather(*(client.get("/api/v1/users/me") for _ in range(4)))

    assert all(response.status_code == 200 for response in responses)
    assert len(sent) == 1


async def test_nobody_is_emailed_when_no_address_is_set(
    make_client: ClientFactory, sent: list[dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "signup_alert_emails", [])

    assert (await make_client().get("/api/v1/users/me")).status_code == 200

    assert sent == []


async def test_a_failed_alert_does_not_break_the_sign_in(
    make_client: ClientFactory, sent: list[dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fail(**_: str) -> None:
        raise RuntimeError("mail service is down")

    monkeypatch.setattr(users_service, "send_email", fail)

    assert (await make_client().get("/api/v1/users/me")).status_code == 200
