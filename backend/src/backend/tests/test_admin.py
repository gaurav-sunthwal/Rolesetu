"""The admin panel's routes: who gets in, what they see, and that it is recorded."""

from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from backend.core.config import get_settings
from backend.db.session import get_sessionmaker
from backend.modules.admin.models import AdminAction
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
    admin: AsyncClient, client: AsyncClient
) -> None:
    await client.put("/api/v1/profile/me", json=PROFILE)
    users = (await admin.get(f"{ADMIN}/users", params={"q": email_of(client)})).json()["items"]
    user_id = users[0]["id"]

    wrong = await admin.delete(f"{ADMIN}/users/{user_id}", params={"confirm_email": "no@x.com"})
    assert wrong.status_code == 422

    done = await admin.delete(
        f"{ADMIN}/users/{user_id}", params={"confirm_email": email_of(client)}
    )
    assert done.status_code == 204
    assert (await admin.get(f"{ADMIN}/users/{user_id}")).status_code == 404
    assert ("user.delete", user_id) in await actions_by(admin)


async def test_the_audit_log_lists_what_admins_did(admin: AsyncClient) -> None:
    await admin.get(f"{ADMIN}/waitlist")
    logged = (await admin.get(f"{ADMIN}/audit")).json()["items"]
    assert any(
        item["action"] == "waitlist.view" and item["admin_email"] == email_of(admin)
        for item in logged
    )
