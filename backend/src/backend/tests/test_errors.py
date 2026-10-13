"""Recording what went wrong, and showing it in the admin panel."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select

from backend.core.config import get_settings
from backend.db.session import get_sessionmaker
from backend.modules.admin.models import AdminAction
from backend.modules.errors import service as errors_service
from backend.modules.errors.models import ErrorEvent
from backend.modules.profiles import service as profiles_service
from backend.tests.conftest import ClientFactory

pytestmark = pytest.mark.records_errors

ERRORS = "/api/v1/admin/errors"


@pytest.fixture
async def source() -> AsyncGenerator[str]:
    """A source name of this test's own, so its events can be found and removed."""
    name = f"t-{uuid.uuid4().hex[:12]}"
    yield name
    async with get_sessionmaker()() as db:
        await db.execute(delete(ErrorEvent).where(ErrorEvent.source == name))
        await db.commit()


@pytest.fixture
async def admin(
    make_client: ClientFactory, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncClient]:
    client = make_client()
    client.headers["x-test-verified"] = "1"
    email = f"{client.headers['x-test-uid']}@example.com"
    monkeypatch.setattr(get_settings(), "admin_emails", [email])
    yield client
    async with get_sessionmaker()() as db:
        await db.execute(delete(AdminAction).where(AdminAction.admin_email == email))
        await db.commit()


def boom() -> None:
    raise KeyError("missing thing")


async def record_boom(source: str, times: int = 1) -> None:
    for _ in range(times):
        try:
            boom()
        except KeyError as exc:
            await errors_service.record(source=source, exc=exc, message=str(exc), route="/x")


async def count(source: str) -> int:
    async with get_sessionmaker()() as db:
        found = await db.execute(
            select(func.count()).select_from(ErrorEvent).where(ErrorEvent.source == source)
        )
        return found.scalar_one()


async def test_the_same_problem_is_counted_as_one_group(admin: AsyncClient, source: str) -> None:
    await record_boom(source, times=3)
    body = (await admin.get(ERRORS, params={"source": source})).json()
    assert body["by_source"][source] == 3
    assert len(body["groups"]) == 1
    group = body["groups"][0]
    assert group["events"] == 3 and group["code"] == "KeyError" and group["route"] == "/x"

    events = (await admin.get(f"{ERRORS}/{group['fingerprint']}")).json()
    assert len(events) == 3
    # The stack names where it broke, so the fault can be found.
    assert "boom" in events[0]["stack"]


async def test_a_problem_repeating_fast_stops_being_written(
    source: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(errors_service, "MAX_PER_HOUR", 2)
    await record_boom(source, times=5)
    assert await count(source) == 2


async def test_clearing_a_problem_removes_it_and_is_recorded(
    admin: AsyncClient, source: str
) -> None:
    await record_boom(source)
    fingerprint = (await admin.get(ERRORS, params={"source": source})).json()["groups"][0][
        "fingerprint"
    ]
    assert (await admin.delete(f"{ERRORS}/{fingerprint}")).status_code == 204
    assert await count(source) == 0
    assert (await admin.get(f"{ERRORS}/{fingerprint}")).status_code == 404
    logged = (await admin.get("/api/v1/admin/audit")).json()["items"]
    assert any(item["action"] == "errors.clear" for item in logged)


async def test_a_crash_in_a_request_is_recorded_with_its_route(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = f"crash-{uuid.uuid4().hex}"

    async def broken(*_: object, **__: object) -> None:
        raise RuntimeError(marker)

    monkeypatch.setattr(profiles_service, "get_profile", broken)
    with pytest.raises(RuntimeError):
        await client.get("/api/v1/profile/me")

    async with get_sessionmaker()() as db:
        found = (
            await db.execute(select(ErrorEvent).where(ErrorEvent.message == marker))
        ).scalar_one()
        assert (found.source, found.status, found.code) == ("api", 500, "RuntimeError")
        assert found.route == "/api/v1/profile/me" and found.method == "GET"
        await db.delete(found)
        await db.commit()


async def test_an_ordinary_user_cannot_see_errors(client: AsyncClient) -> None:
    assert (await client.get(ERRORS)).status_code == 403
