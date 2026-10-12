"""The browser extension's key: what it can reach, and what it cannot."""

from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.tests.conftest import ClientFactory

BASE = "/api/v1/extension"


def extension_client(token: str) -> AsyncClient:
    """A client signed in with an extension key (no dashboard session)."""
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "x-test-uid": "ignored"},
    )


async def test_connect_issues_a_key_and_reports_status(make_client: ClientFactory) -> None:
    dashboard = make_client()
    assert (await dashboard.get(f"{BASE}/status")).json()["connected"] is False

    connected = await dashboard.post(f"{BASE}/connect")
    assert connected.status_code == 201
    assert connected.json()["token"].startswith("aa_ext_")
    assert (await dashboard.get(f"{BASE}/status")).json()["connected"] is True


async def test_reconnecting_replaces_the_old_key(make_client: ClientFactory) -> None:
    dashboard = make_client()
    first = (await dashboard.post(f"{BASE}/connect")).json()["token"]
    second = (await dashboard.post(f"{BASE}/connect")).json()["token"]
    assert first != second
