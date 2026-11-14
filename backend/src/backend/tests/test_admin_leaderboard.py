"""The admin leaderboard: who uses Rolesetu most, and which features, through the API
and database. Real users share this database, so the tests look for their own
throwaway users in the list rather than at fixed positions."""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from backend.core.config import get_settings
from backend.db.session import get_sessionmaker
from backend.tests.conftest import ClientFactory

URL = "/api/v1/admin/leaderboard"


@pytest.fixture
async def admin_client(
    make_client: ClientFactory, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncClient]:
    client = make_client()
    client.headers["x-test-verified"] = "1"
    monkeypatch.setattr(
        get_settings(), "admin_emails", [f"{client.headers['x-test-uid']}@example.com"]
    )
    yield client


async def user_id_of(client: AsyncClient) -> uuid.UUID:
    return uuid.UUID((await client.get("/api/v1/users/me")).json()["id"])


async def use(
    client: AsyncClient, *, checks: int = 0, ai_answers: int = 0, autofills: int = 0
) -> uuid.UUID:
    """Leaves behind what using these features records."""
    user_id = await user_id_of(client)
    async with get_sessionmaker()() as db:
        for _ in range(checks):
            job_id = uuid.uuid4()
            await db.execute(
                text(
                    "INSERT INTO jobs (id, user_id, jd_text, content_hash) VALUES (:i, :u, 'J', :h)"
                ),
                {"i": job_id, "u": user_id, "h": uuid.uuid4().hex},
            )
            await db.execute(
                text(
                    "INSERT INTO matches (id, user_id, job_id, profile_version, status,"
                    " skill_results, gaps) VALUES (:i, :u, :j, 1, 'completed', '[]', '[]')"
                ),
                {"i": uuid.uuid4(), "u": user_id, "j": job_id},
            )
        for _ in range(ai_answers):
            await db.execute(
                text(
                    "INSERT INTO ai_calls (id, user_id, source, purpose, own_key, ok, duration_ms)"
                    " VALUES (:i, :u, 'extension', 'form-answer', false, true, 10)"
                ),
                {"i": uuid.uuid4(), "u": user_id},
            )
        for _ in range(autofills):
            await db.execute(
                text(
                    "INSERT INTO ext_events (id, user_id, name) VALUES (:i, :u, 'autofill_filled')"
                ),
                {"i": uuid.uuid4(), "u": user_id},
            )
        await db.commit()
    return user_id


def row_of(body: dict[str, Any], user_id: uuid.UUID) -> dict[str, Any]:
    return next(row for row in body["users"] if row["user_id"] == str(user_id))


async def test_only_admins_see_it(client: AsyncClient) -> None:
    assert (await client.get(URL)).status_code == 403


async def test_users_are_ranked_by_use_with_their_top_features(
    make_client: ClientFactory, admin_client: AsyncClient
) -> None:
    busy, light = make_client(), make_client()
    busy_id = await use(busy, checks=4, ai_answers=2, autofills=1)
    light_id = await use(light, checks=1)

    response = await admin_client.get(URL, params={"days": 1, "limit": 100})
    assert response.status_code == 200, response.text
    body = response.json()

    top = row_of(body, busy_id)
    assert top["total_actions"] == 7
    assert top["features"] == {"job_check": 4, "ai_answer": 2, "autofill": 1}
    assert top["top_features"] == ["job_check", "ai_answer", "autofill"]
    assert top["active_days"] == 1 and top["plan"] == "free"
    assert top["email"].endswith("@example.com")

    other = row_of(body, light_id)
    assert other["total_actions"] == 1 and other["top_features"] == ["job_check"]
    assert top["rank"] < other["rank"]

    keys = [feature["key"] for feature in body["features"]]
    assert "job_check" in keys and "ai_answer" in keys
    assert body["totals"]["job_check"] >= 5


async def test_a_user_with_no_activity_is_not_listed(
    make_client: ClientFactory, admin_client: AsyncClient
) -> None:
    idle_id = await user_id_of(make_client())
    body = (await admin_client.get(URL, params={"days": 1, "limit": 100})).json()
    assert all(row["user_id"] != str(idle_id) for row in body["users"])
