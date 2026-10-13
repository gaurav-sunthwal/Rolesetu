"""Joining the list of people to email when the extension is released."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from backend.core.client_ip import hash_ip
from backend.db.session import get_sessionmaker
from backend.main import app
from backend.modules.waitlist import service as waitlist_service
from backend.modules.waitlist.models import WaitlistEntry

WAITLIST = "/api/v1/public/extension-waitlist"


def address() -> str:
    return f"Test-{uuid.uuid4()}@Example.com"


async def times_listed(email: str) -> int:
    async with get_sessionmaker()() as db:
        found = await db.execute(
            select(func.count()).select_from(WaitlistEntry).where(WaitlistEntry.email == email)
        )
        return found.scalar_one()


@pytest.fixture
async def visitor() -> AsyncGenerator[AsyncClient]:
    """Someone who is not signed in, with an address of their own."""
    ip = f"203.0.113.{uuid.uuid4()}"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"x-forwarded-for": ip}
    ) as client:
        yield client
    async with get_sessionmaker()() as db:
        await db.execute(delete(WaitlistEntry).where(WaitlistEntry.client_hash == hash_ip(ip)))
        await db.commit()


async def test_a_visitor_joins_without_signing_in(visitor: AsyncClient) -> None:
    email = address()
    response = await visitor.post(WAITLIST, json={"email": email})
    assert response.status_code == 200 and response.json() == {"joined": True}
    # Stored in lower case, whatever was typed.
    assert await times_listed(email.lower()) == 1


async def test_joining_twice_keeps_one_entry_and_says_the_same(visitor: AsyncClient) -> None:
    email = address()
    first = await visitor.post(WAITLIST, json={"email": email})
    again = await visitor.post(WAITLIST, json={"email": email.upper()})
    assert first.json() == again.json() == {"joined": True}
    assert await times_listed(email.lower()) == 1


async def test_something_that_is_not_an_email_is_refused(visitor: AsyncClient) -> None:
    assert (await visitor.post(WAITLIST, json={"email": "not an email"})).status_code == 422


async def test_one_visitor_cannot_fill_the_list(
    visitor: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(waitlist_service, "MAX_JOINS_PER_HOUR", 2)
    for _ in range(2):
        assert (await visitor.post(WAITLIST, json={"email": address()})).status_code == 200
    assert (await visitor.post(WAITLIST, json={"email": address()})).status_code == 429
