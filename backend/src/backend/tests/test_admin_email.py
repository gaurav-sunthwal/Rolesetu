"""Emailing people from the admin panel. Nothing is really sent: the email
service is replaced by a stand-in that remembers what it was given.
"""

import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.modules.admin import emails
from backend.modules.admin import repository as admin_repository
from backend.modules.admin import service as admin_service
from backend.tests.conftest import ClientFactory

ADMIN = "/api/v1/admin"
PROFILE = {"full_name": "Asha Rao", "skills": [{"id": "s1", "name": "React"}]}
NOTE = {"subject": "Hello {first_name}", "message": "Hi {first_name},\n\nTry the extension."}


@dataclass
class Outbox:
    sent: list[dict[str, object]] = field(default_factory=list)
    fail: bool = False

    async def send(self, **email: object) -> None:
        if self.fail:
            raise RuntimeError("provider down")
        self.sent.append(email)


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> Outbox:
    box = Outbox()
    monkeypatch.setattr(admin_service, "send_email", box.send)
    monkeypatch.setattr(get_settings(), "resend_api_key", "test-key")
    monkeypatch.setattr(admin_service, "SECONDS_BETWEEN_SENDS", 0)
    return box


@pytest.fixture
async def admin(
    make_client: ClientFactory, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncClient]:
    client = make_client()
    client.headers["x-test-verified"] = "1"
    email = f"{client.headers['x-test-uid']}@example.com"
    monkeypatch.setattr(get_settings(), "admin_emails", [email])
    yield client


def email_of(client: AsyncClient) -> str:
    return f"{client.headers['x-test-uid']}@example.com"


async def user_id(admin: AsyncClient, person: AsyncClient) -> str:
    found = await admin.get(f"{ADMIN}/users", params={"q": email_of(person)})
    return str(found.json()["items"][0]["id"])


async def test_an_admin_emails_one_person_by_first_name(
    admin: AsyncClient, client: AsyncClient, outbox: Outbox
) -> None:
    await client.put("/api/v1/profile/me", json=PROFILE)
    target = await user_id(admin, client)

    sent = await admin.post(f"{ADMIN}/users/{target}/email", json=NOTE)
    assert sent.status_code == 200 and sent.json()["status"] == "sent"
    assert len(outbox.sent) == 1
    email = outbox.sent[0]
    assert email["to"] == email_of(client) and email["subject"] == "Hello Asha"
    text = str(email["text"])
    assert "Hi Asha," in text and get_settings().extension_store_url in text
    assert email["html"] is None and email["sender_name"] == emails.SENDER_NAME

    detail = (await admin.get(f"{ADMIN}/users/{target}")).json()
    assert [item["subject"] for item in detail["panel_emails"]] == ["Hello Asha"]
    assert detail["user"]["last_emailed_at"] is not None


async def test_the_same_person_is_not_emailed_twice_in_a_day(
    admin: AsyncClient, client: AsyncClient, outbox: Outbox
) -> None:
    await client.put("/api/v1/profile/me", json=PROFILE)
    target = await user_id(admin, client)
    assert (await admin.post(f"{ADMIN}/users/{target}/email", json=NOTE)).status_code == 200
    again = await admin.post(f"{ADMIN}/users/{target}/email", json=NOTE)
    assert again.status_code == 409 and len(outbox.sent) == 1


async def test_a_failed_send_is_recorded_not_hidden(
    admin: AsyncClient, client: AsyncClient, outbox: Outbox
) -> None:
    await client.put("/api/v1/profile/me", json=PROFILE)
    target = await user_id(admin, client)
    outbox.fail = True
    sent = await admin.post(f"{ADMIN}/users/{target}/email", json=NOTE)
    assert sent.status_code == 200 and sent.json()["status"] == "failed"


async def test_nothing_is_sent_when_email_is_not_set_up(
    admin: AsyncClient, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "resend_api_key", None)
    monkeypatch.setattr(get_settings(), "gmail_sender_refresh_token", None)
    await client.put("/api/v1/profile/me", json=PROFILE)
    target = await user_id(admin, client)
    refused = await admin.post(f"{ADMIN}/users/{target}/email", json=NOTE)
    assert refused.status_code == 422 and "GMAIL_SENDER_REFRESH_TOKEN" in refused.json()["detail"]


async def test_people_without_the_extension_can_be_listed(
    admin: AsyncClient, client: AsyncClient
) -> None:
    await client.put("/api/v1/profile/me", json=PROFILE)
    found = await admin.get(
        f"{ADMIN}/users", params={"q": email_of(client), "extension": "missing"}
    )
    assert [row["email"] for row in found.json()["items"]] == [email_of(client)]


async def test_the_bulk_send_writes_only_to_people_not_written_to_lately(
    admin: AsyncClient, make_client: ClientFactory, outbox: Outbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two new people; one was already written to today.
    first, second = make_client(), make_client()
    for person in (first, second):
        await person.put("/api/v1/profile/me", json=PROFILE)
    await admin.post(f"{ADMIN}/users/{await user_id(admin, first)}/email", json=NOTE)
    outbox.sent.clear()

    # Only these two count, whoever else is in the database.
    ours = {email_of(first), email_of(second)}
    real = admin_repository.nudge_recipients

    async def only_ours(
        db: AsyncSession, quiet_since: datetime, limit: int
    ) -> list[tuple[Any, ...]]:
        rows = await real(db, quiet_since, limit)
        return [row for row in rows if row[0].email in ours]

    monkeypatch.setattr(admin_repository, "nudge_recipients", only_ours)
    monkeypatch.setattr(admin_service, "MAX_PER_SEND", 10_000)

    queued = await admin.post(f"{ADMIN}/emails/extension-nudge", json=NOTE)
    assert queued.status_code == 200 and queued.json()["queued"] >= 1
    assert [email["to"] for email in outbox.sent] == [email_of(second)]


async def test_an_ordinary_user_cannot_send(client: AsyncClient, outbox: Outbox) -> None:
    assert (await client.post(f"{ADMIN}/emails/extension-nudge", json=NOTE)).status_code == 403
    assert outbox.sent == []


def test_the_note_is_plain_text_with_the_store_link_and_sign_off() -> None:
    note = emails.extension_nudge(
        subject="Hi {first_name}",
        message="Hi {first_name},\n\nOne <b>bold</b> line",
        name="Asha",
        store_url="https://store.example/x",
    )
    assert note.subject == "Hi Asha"
    assert note.text.startswith("Hi Asha,\n\nOne <b>bold</b> line\n")
    assert "https://store.example/x" in note.text and "Gaurav Sunthwal" in note.text
    assert emails.first_name("  Asha  Rao ") == "Asha" and emails.first_name(None) == "there"


async def test_templates_are_filled_in_for_the_person(
    admin: AsyncClient, client: AsyncClient
) -> None:
    await client.put("/api/v1/profile/me", json=PROFILE)
    target = await user_id(admin, client)
    found = await admin.get(f"{ADMIN}/users/{target}/email-templates")
    assert found.status_code == 200
    by_id = {t["id"]: t for t in found.json()}
    # A new account: nothing checked yet, and no extension.
    assert set(by_id) == {"stuck", "extension"}
    assert by_id["stuck"]["recommended"] and "signed up today" in by_id["stuck"]["message"]
    assert by_id["extension"]["kind"] == "extension_nudge"


async def test_a_founder_note_has_no_store_link(
    admin: AsyncClient, client: AsyncClient, outbox: Outbox
) -> None:
    await client.put("/api/v1/profile/me", json=PROFILE)
    target = await user_id(admin, client)
    note = {**NOTE, "kind": "founder_note"}
    sent = await admin.post(f"{ADMIN}/users/{target}/email", json=note)
    assert sent.status_code == 200 and sent.json()["kind"] == "founder_note"
    text = str(outbox.sent[0]["text"])
    assert get_settings().extension_store_url not in text
    assert text.rstrip().endswith("Founder, Rolesetu")


async def test_only_an_admin_sees_templates(client: AsyncClient) -> None:
    found = await client.get(f"{ADMIN}/users/{uuid.uuid4()}/email-templates")
    assert found.status_code == 403


def test_templates_follow_what_the_person_did() -> None:
    now = datetime(2026, 10, 24, tzinfo=UTC)
    usage = emails.Usage(
        joined_at=now - timedelta(days=9), job_checks=23, applications=4, has_extension=True
    )
    found = {t.id: t for t in emails.templates_for(usage, now)}
    assert set(found) == {"experience", "improve", "applications"}
    assert [t.id for t in found.values() if t.recommended] == ["applications"]
    assert "joined 9 days ago and have checked 23 jobs" in found["experience"].message
    assert "tracked 4 applications" in found["applications"].message


def test_a_subject_without_a_name_drops_the_greeting() -> None:
    note = emails.founder_note(
        subject="{first_name}, how has Rolesetu been so far?",
        message="Hi {first_name},",
        name="there",
    )
    assert note.subject == "How has Rolesetu been so far?"
    assert note.text.startswith("Hi there,")
