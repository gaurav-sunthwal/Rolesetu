"""The founder's one-time note, a few hours after someone first signs in.

Nothing is really sent: the email service is replaced by a stand-in. Test
accounts are dated back to 2001 and each round is run "in 2001", so real
accounts in the database can never be picked.
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from backend.core.config import get_settings
from backend.db.session import get_sessionmaker
from backend.modules.feedback import emails
from backend.modules.feedback import service as feedback
from backend.modules.users.models import User

JOINED = datetime(2001, 3, 1, 9, 0, tzinfo=UTC)
STORE = "https://chromewebstore.google.com/detail/test"


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    sent: list[dict[str, object]] = []

    async def record(**message: object) -> None:
        sent.append(message)

    monkeypatch.setattr(feedback, "send_email", record)
    monkeypatch.setattr(get_settings(), "resend_api_key", "test-key")
    monkeypatch.setattr(get_settings(), "feedback_email_delay_hours", 3.0)
    return sent


async def joined_in_2001(client: AsyncClient) -> None:
    """Signs the test user in, then dates their account back to JOINED."""
    assert (await client.get("/api/v1/users/me")).status_code == 200
    async with get_sessionmaker()() as db:
        await db.execute(
            update(User)
            .where(User.firebase_uid == client.headers["x-test-uid"])
            .values(created_at=JOINED)
        )
        await db.commit()


def to(outbox: list[dict[str, object]], client: AsyncClient) -> list[dict[str, object]]:
    address = f"{client.headers['x-test-uid']}@example.com"
    return [message for message in outbox if message["to"] == address]


async def test_sent_once_three_hours_after_the_first_sign_in(
    client: AsyncClient, outbox: list[dict[str, object]]
) -> None:
    await joined_in_2001(client)

    await feedback.send_due(JOINED + timedelta(hours=2))
    assert to(outbox, client) == []

    await feedback.send_due(JOINED + timedelta(hours=3, minutes=5))
    await feedback.send_due(JOINED + timedelta(hours=5))
    mine = to(outbox, client)
    assert len(mine) == 1
    assert mine[0]["html"] is None and mine[0]["sender_name"] == emails.SENDER_NAME


async def test_without_the_extension_it_points_to_the_extension(
    client: AsyncClient, outbox: list[dict[str, object]]
) -> None:
    await joined_in_2001(client)
    await feedback.send_due(JOINED + timedelta(hours=4))
    (message,) = to(outbox, client)
    assert message["subject"] == emails.WITHOUT_EXTENSION_SUBJECT
    assert get_settings().extension_store_url in str(message["text"])


async def test_with_the_extension_it_only_asks_how_it_went(
    client: AsyncClient, outbox: list[dict[str, object]]
) -> None:
    await joined_in_2001(client)
    assert (await client.post("/api/v1/extension/connect")).status_code == 201
    await feedback.send_due(JOINED + timedelta(hours=4))
    (message,) = to(outbox, client)
    assert message["subject"] == emails.WITH_EXTENSION_SUBJECT
    assert "http" not in str(message["text"])


async def test_people_who_joined_long_ago_are_left_alone(
    client: AsyncClient, outbox: list[dict[str, object]]
) -> None:
    await joined_in_2001(client)
    await feedback.send_due(JOINED + timedelta(days=4))
    assert to(outbox, client) == []


async def test_a_failed_send_is_not_retried(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, outbox: list[dict[str, object]]
) -> None:
    await joined_in_2001(client)

    async def fail(**_: object) -> None:
        raise RuntimeError("mail service is down")

    async def record(**message: object) -> None:
        outbox.append(message)

    monkeypatch.setattr(feedback, "send_email", fail)
    assert await feedback.send_due(JOINED + timedelta(hours=4)) == 0
    monkeypatch.setattr(feedback, "send_email", record)
    await feedback.send_due(JOINED + timedelta(hours=5))
    assert to(outbox, client) == []


async def test_nothing_happens_when_email_is_not_set_up(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "resend_api_key", None)
    monkeypatch.setattr(get_settings(), "gmail_sender_refresh_token", None)
    await joined_in_2001(client)
    assert await feedback.send_due(JOINED + timedelta(hours=4)) == 0


def test_the_note_greets_by_first_name() -> None:
    note = emails.first_use_feedback(full_name="Asha Rao", has_extension=False, store_url=STORE)
    assert note.subject == "Asha, thanks for trying Rolesetu"
    assert note.text.startswith("Hi Asha,")
    assert STORE in note.text and "Gaurav Sunthwal" in note.text


def test_without_a_name_it_still_reads_well() -> None:
    note = emails.first_use_feedback(full_name=None, has_extension=True, store_url=STORE)
    assert note.subject == emails.WITH_EXTENSION_SUBJECT
    assert note.text.startswith("Hi there,")
