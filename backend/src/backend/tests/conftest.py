import os

# Before any app import: keep SQL echo out of test output.
os.environ["DEBUG"] = "false"

import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from backend.core.security import CurrentUser, get_current_user
from backend.db.session import get_engine, get_sessionmaker
from backend.main import app
from backend.modules.users.models import User

ClientFactory = Callable[[], AsyncClient]


@pytest.fixture(scope="session", autouse=True)
async def _dispose_engine() -> AsyncGenerator[None]:
    yield
    await get_engine().dispose()


@pytest.fixture
async def make_client() -> AsyncGenerator[ClientFactory]:
    """Builds API clients, each signed in as its own throwaway user.

    Auth is swapped at the dependency (the real one needs a Google-signed
    token), so everything below it, including user scoping, runs for real
    against the database. Users are deleted afterwards and take their rows
    with them.
    """
    uids: list[str] = []
    clients: list[AsyncClient] = []

    def factory() -> AsyncClient:
        uid = f"test-{uuid.uuid4()}"
        uids.append(uid)

        async def fake_user() -> CurrentUser:
            return CurrentUser(uid=uid, email=f"{uid}@example.com")

        # Per-client auth via a header the override reads, so two users can
        # share one app instance in the same test.
        client = AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers={"x-test-uid": uid}
        )
        clients.append(client)
        return client

    from fastapi import Request

    async def current_user_from_header(request: Request) -> CurrentUser:
        uid = request.headers["x-test-uid"]
        # A test that needs a verified sign-in (the admin routes) says so in a header.
        verified = request.headers.get("x-test-verified") == "1"
        return CurrentUser(uid=uid, email=f"{uid}@example.com", email_verified=verified)

    app.dependency_overrides[get_current_user] = current_user_from_header
    try:
        yield factory
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        for client in clients:
            await client.aclose()
        if uids:
            async with get_sessionmaker()() as db:
                await db.execute(delete(User).where(User.firebase_uid.in_(uids)))
                await db.commit()


@pytest.fixture
async def client(make_client: ClientFactory) -> AsyncClient:
    return make_client()
