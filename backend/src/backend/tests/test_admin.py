"""The admin panel's routes: who gets in, what they see, and that it is recorded."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from backend.core import firebase_accounts, storage
from backend.core.config import get_settings
from backend.db.session import get_sessionmaker
from backend.modules.admin.models import AdminAction
from backend.modules.resumes.models import ResumeFile
from backend.tests.conftest import ClientFactory

ADMIN = "/api/v1/admin"
PROFILE = {
    "full_name": "Asha Rao",
    "skills": [{"id": "s1", "name": "React", "level": "intermediate"}],
}
JD = "We are hiring a Frontend Engineer. You must know React and Docker. " + "Build features. " * 12


def email_of(client: AsyncClient) -> str:
    return f"{client.headers['x-test-uid']}@example.com"


@pytest.fixture
async def admin(
    make_client: ClientFactory, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncClient]:
    """A signed-in, verified account that is on the admin list."""
    client = make_client()
    client.headers["x-test-verified"] = "1"
    # Upper case on purpose: the list is matched without regard to case.
    monkeypatch.setattr(get_settings(), "admin_emails", [email_of(client).upper()])
    yield client
    async with get_sessionmaker()() as db:
        await db.execute(delete(AdminAction).where(AdminAction.admin_email == email_of(client)))
        await db.commit()


async def actions_by(client: AsyncClient) -> list[tuple[str, str]]:
    async with get_sessionmaker()() as db:
        found = await db.execute(
            select(AdminAction.action, AdminAction.target_id)
            .where(AdminAction.admin_email == email_of(client))
            .order_by(AdminAction.created_at)
        )
        return [(action, target) for action, target in found]


@pytest.mark.parametrize("path", ["/me", "/stats", "/users", "/waitlist", "/audit"])
async def test_an_ordinary_user_is_refused_everywhere(client: AsyncClient, path: str) -> None:
    assert (await client.get(f"{ADMIN}{path}")).status_code == 403


async def test_a_listed_email_that_is_not_verified_is_refused(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "admin_emails", [email_of(client)])
    assert (await client.get(f"{ADMIN}/me")).status_code == 403


async def test_an_admin_gets_in_and_sees_totals(admin: AsyncClient) -> None:
    assert (await admin.get(f"{ADMIN}/me")).json() == {"email": email_of(admin)}
    stats = (await admin.get(f"{ADMIN}/stats")).json()
    assert stats["users"] >= 1 and len(stats["daily"]) == 14
    assert stats["extension_connected"] >= stats["extension_active_week"] >= 0


async def test_an_admin_finds_a_user_and_opening_them_is_recorded(
    admin: AsyncClient, client: AsyncClient
) -> None:
    await client.put("/api/v1/profile/me", json=PROFILE)
    await client.post("/api/v1/matches", json={"jd_text": JD})

    found = (await admin.get(f"{ADMIN}/users", params={"q": email_of(client)})).json()["items"]
    assert len(found) == 1
    row = found[0]
    assert row["has_profile"] and row["job_checks"] == 1 and not row["gmail_connected"]

    detail = (await admin.get(f"{ADMIN}/users/{row['id']}")).json()
    assert detail["profile"]["full_name"] == "Asha Rao"
    assert len(detail["job_checks"]) == 1
    # Nothing read from the user's mailbox is part of what an admin gets.
    assert "emails" not in detail and "messages" not in detail
    assert ("user.view", row["id"]) in await actions_by(admin)


async def test_deleting_an_account_needs_its_email_and_removes_its_data(
    admin: AsyncClient, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "firebase_service_account_json", None)
    monkeypatch.setattr(get_settings(), "firebase_service_account_path", None)
    await client.put("/api/v1/profile/me", json=PROFILE)
    users = (await admin.get(f"{ADMIN}/users", params={"q": email_of(client)})).json()["items"]
    user_id = users[0]["id"]

    wrong = await admin.delete(f"{ADMIN}/users/{user_id}", params={"confirm_email": "no@x.com"})
    assert wrong.status_code == 422

    done = await admin.delete(
        f"{ADMIN}/users/{user_id}", params={"confirm_email": email_of(client)}
    )
    assert done.status_code == 200
    # No Firebase key in tests: the data is gone and the admin is told to finish by hand.
    assert done.json()["sign_in_removed"] is False
    assert (await admin.get(f"{ADMIN}/users/{user_id}")).status_code == 404
    assert ("user.delete", user_id) in await actions_by(admin)


async def test_deleting_an_account_also_removes_its_sign_in(
    admin: AsyncClient, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    removed: list[str] = []

    async def remove(uid: str) -> None:
        removed.append(uid)

    monkeypatch.setattr(firebase_accounts, "delete_sign_in", remove)
    await client.put("/api/v1/profile/me", json=PROFILE)
    users = (await admin.get(f"{ADMIN}/users", params={"q": email_of(client)})).json()["items"]

    done = await admin.delete(
        f"{ADMIN}/users/{users[0]['id']}", params={"confirm_email": email_of(client)}
    )
    assert done.json() == {"sign_in_removed": True, "note": None}
    assert removed == [client.headers["x-test-uid"]]


async def test_the_audit_log_lists_what_admins_did(admin: AsyncClient) -> None:
    await admin.get(f"{ADMIN}/waitlist")
    logged = (await admin.get(f"{ADMIN}/audit")).json()["items"]
    assert any(
        item["action"] == "waitlist.view" and item["admin_email"] == email_of(admin)
        for item in logged
    )


async def test_an_admin_sees_who_connected_the_extension(
    admin: AsyncClient, client: AsyncClient
) -> None:
    async def user_row() -> dict[str, object]:
        found = await admin.get(f"{ADMIN}/users", params={"q": email_of(client)})
        row: dict[str, object] = found.json()["items"][0]
        return row

    await client.put("/api/v1/profile/me", json=PROFILE)
    before = (await admin.get(f"{ADMIN}/stats")).json()["extension_connected"]
    assert not (await user_row())["extension_connected"]

    assert (await client.post("/api/v1/extension/connect")).status_code == 201
    assert (await user_row())["extension_connected"]
    assert (await admin.get(f"{ADMIN}/stats")).json()["extension_connected"] >= before + 1


async def add_resume(client: AsyncClient) -> tuple[str, str]:
    """A resume row for this user (the file itself is faked in storage)."""
    user_id = (await client.get("/api/v1/users/me")).json()["id"]
    resume = ResumeFile(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        storage_key=f"resumes/{user_id}/test.pdf",
        filename="Asha Rao CV.pdf",
        size_bytes=12,
    )
    async with get_sessionmaker()() as db:
        db.add(resume)
        await db.commit()
    return user_id, str(resume.id)


async def test_an_admin_can_open_a_resume_and_it_is_recorded(
    admin: AsyncClient, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_file(key: str) -> bytes:
        return b"%PDF-1.7 test"

    monkeypatch.setattr(storage, "get_file", fake_file)
    user_id, resume_id = await add_resume(client)

    opened = await admin.get(f"{ADMIN}/users/{user_id}/resumes/{resume_id}/file")
    assert opened.status_code == 200
    assert opened.headers["content-type"] == "application/pdf"
    assert opened.headers["cache-control"] == "private, no-store"
    assert opened.content == b"%PDF-1.7 test"
    assert ("resume.view", user_id) in await actions_by(admin)

    # A resume is only found under the account it belongs to.
    other = await admin.get(f"{ADMIN}/users/{uuid.uuid4()}/resumes/{resume_id}/file")
    assert other.status_code == 404


async def test_an_ordinary_user_cannot_open_anyones_resume(
    make_client: ClientFactory,
) -> None:
    owner, stranger = make_client(), make_client()
    user_id, resume_id = await add_resume(owner)
    refused = await stranger.get(f"{ADMIN}/users/{user_id}/resumes/{resume_id}/file")
    assert refused.status_code == 403
