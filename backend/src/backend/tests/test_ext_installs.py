"""Following installs before sign-in: what may be sent without an account, the
limits on it, linking to the account on connect, and the admin view."""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import delete

from backend.core.config import get_settings
from backend.db.session import get_sessionmaker
from backend.modules.ext_installs import service
from backend.modules.ext_installs.models import ExtInstall, ExtInstallEvent
from backend.modules.ext_installs.repository import _reached
from backend.modules.ext_installs.schemas import InstallEventsWrite
from backend.tests.conftest import ClientFactory

INSTALLS = "/api/v1/extension/installs"
EVENTS = "/api/v1/extension/events"
ADMIN = "/api/v1/admin"


def event(name: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "id": str(uuid.uuid4()), "version": "1.3.0", **extra}


def batch(install_id: str, *events: dict[str, Any], **info: Any) -> dict[str, Any]:
    return {"install": {"id": install_id, **info}, "events": list(events)}


# ── What may be sent (no database) ────────────────────────────────────────────


def test_an_install_describes_itself_in_short_plain_words() -> None:
    install_id = str(uuid.uuid4())
    sent = InstallEventsWrite.model_validate(
        batch(install_id, browser="Google Chrome 142", os="win", timezone="Europe/Bucharest")
    )
    assert sent.install.timezone == "Europe/Bucharest"

    with pytest.raises(ValidationError):  # not an id the extension makes
        InstallEventsWrite.model_validate(batch("not-an-id"))
    with pytest.raises(ValidationError):  # markup is not a browser name
        InstallEventsWrite.model_validate(batch(install_id, browser="<script>"))
    with pytest.raises(ValidationError):  # at most 50 events a request
        InstallEventsWrite.model_validate(
            batch(install_id, *(event("popup_opened") for _ in range(51)))
        )


def test_the_furthest_step_is_named_for_each_install() -> None:
    assert _reached({"extension_installed"}, connected=False) == "Installed"
    assert _reached({"setup_opened", "setup_page_seen"}, connected=False) == "Setup page loaded"
    assert _reached({"signup_started", "sign_in_failed"}, connected=False) == "Sign-in failed"
    assert (
        _reached({"signed_in", "connect_failed"}, connected=False) == "Signed in, connecting failed"
    )
    assert _reached({"signed_in"}, connected=True) == "Extension connected"
    assert _reached({"job_detected"}, connected=True) == "Used it on a job page"


# ── Stored and read back (needs migration d4f6b8c0e2a5 applied) ──────────────


@pytest.fixture
async def install_ids() -> AsyncGenerator[list[str]]:
    """Installs made by a test, deleted afterwards (installs without an account
    are not removed with the test users)."""
    made: list[str] = []
    yield made
    async with get_sessionmaker()() as db:
        await db.execute(delete(ExtInstallEvent).where(ExtInstallEvent.install_id.in_(made)))
        await db.execute(delete(ExtInstall).where(ExtInstall.install_id.in_(made)))
        await db.commit()


@pytest.fixture
def new_install(install_ids: list[str]) -> str:
    install_id = str(uuid.uuid4())
    install_ids.append(install_id)
    return install_id


@pytest.fixture
async def admin(make_client: ClientFactory, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    client = make_client()
    client.headers["x-test-verified"] = "1"
    monkeypatch.setattr(
        get_settings(), "admin_emails", [f"{client.headers['x-test-uid']}@example.com"]
    )
    return client


@pytest.fixture
def anonymous(client: AsyncClient) -> AsyncClient:
    # Each test from its own address, so the per-address limit is the test's own.
    client.headers["x-real-ip"] = f"test-{uuid.uuid4()}"
    return client


async def test_an_install_is_followed_from_install_to_its_first_job_page(
    anonymous: AsyncClient, client: AsyncClient, admin: AsyncClient, new_install: str
) -> None:
    before = batch(
        new_install,
        event("extension_installed"),
        event("setup_opened", props={"why": "install"}),
        version="1.3.0",
        browser="Google Chrome 142",
        os="linux",
        language="en-GB",
        timezone="Europe/Bucharest",
    )
    assert (await anonymous.post(f"{INSTALLS}/events", json=before)).status_code == 204
    # Retried: stored once.
    assert (await anonymous.post(f"{INSTALLS}/events", json=before)).status_code == 204
    # The website's setup page knows only the id; it must not erase what the extension said.
    seen = batch(new_install, {"name": "setup_page_seen"}, automated=False)
    assert (await anonymous.post(f"{INSTALLS}/events", json=seen)).status_code == 204

    # Connected: the account's events now carry the install, which links the two.
    client.headers["x-test-extension"] = "1"
    connected = {"events": [event("job_detected", host="wellfound.com")], "install": new_install}
    assert (await client.post(EVENTS, json=connected)).status_code == 204

    stats = (await admin.get(f"{ADMIN}/ext-installs?hours=1")).json()
    row = next(row for row in stats["recent"] if row["install_id"] == new_install)
    assert row["timezone"] == "Europe/Bucharest" and row["os"] == "linux"
    assert row["reached"] == "Used it on a job page"
    assert row["user_id"] is not None
    steps = {step["step"]: step["installs"] for step in stats["funnel"]}
    assert steps["connected"] >= 1 and steps["used"] >= 1
    assert any(group["label"] == "Europe/Bucharest" for group in stats["by_timezone"])

    journey = (await admin.get(f"{ADMIN}/ext-installs/{new_install}/events")).json()
    names = [step["name"] for step in journey]
    assert names.count("setup_opened") == 1
    assert {"extension_installed", "setup_page_seen", "job_detected"} <= set(names)


async def test_an_uninstall_is_recorded_once_and_asks_why(
    anonymous: AsyncClient, admin: AsyncClient, new_install: str
) -> None:
    await anonymous.post(
        f"{INSTALLS}/events", json=batch(new_install, event("extension_installed"))
    )

    for _ in range(2):
        response = await anonymous.get(f"{INSTALLS}/{new_install}/uninstalled?v=1.3.0")
        assert response.status_code == 303
        assert response.headers["location"].endswith(f"/goodbye?install={new_install}")
    reason = batch(new_install, {"name": "uninstall_reason", "props": {"reason": "no_account"}})
    assert (await anonymous.post(f"{INSTALLS}/events", json=reason)).status_code == 204

    journey = (await admin.get(f"{ADMIN}/ext-installs/{new_install}/events")).json()
    assert [step["name"] for step in journey].count("extension_uninstalled") == 1
    stats = (await admin.get(f"{ADMIN}/ext-installs?hours=1")).json()
    assert any(row["label"] == "no_account" for row in stats["uninstall_reasons"])
    row = next(row for row in stats["recent"] if row["install_id"] == new_install)
    assert row["uninstalled_at"] is not None


async def test_one_address_cannot_register_installs_without_end(
    anonymous: AsyncClient, install_ids: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "MAX_NEW_INSTALLS_PER_HOUR", 2)
    statuses = []
    for _ in range(3):
        install_ids.append(install_id := str(uuid.uuid4()))
        sent = await anonymous.post(f"{INSTALLS}/events", json=batch(install_id))
        statuses.append(sent.status_code)
    assert statuses == [204, 204, 429]


async def test_an_install_linked_to_one_account_is_not_taken_by_another(
    make_client: ClientFactory, admin: AsyncClient, new_install: str
) -> None:
    first, second = make_client(), make_client()
    for client in (first, second):
        client.headers["x-test-extension"] = "1"
        sent = {"events": [event("popup_opened")], "install": new_install}
        assert (await client.post(EVENTS, json=sent)).status_code == 204

    stats = (await admin.get(f"{ADMIN}/ext-installs?hours=1")).json()
    row = next(row for row in stats["recent"] if row["install_id"] == new_install)
    first.headers.pop("x-test-extension")  # reading the account is the dashboard's
    first_user = (await first.get("/api/v1/users/me")).json()["id"]
    assert row["user_id"] == first_user


async def test_people_using_it_without_an_account_are_counted_apart(
    anonymous: AsyncClient, client: AsyncClient, admin: AsyncClient, install_ids: list[str]
) -> None:
    using, bot, connected = (str(uuid.uuid4()) for _ in range(3))
    install_ids.extend([using, bot, connected])
    sent = batch(
        using,
        event("extension_installed"),
        event("job_detected", host="linkedin.com"),
        event("job_previewed", count=6),
        event("setup_opened", props={"why": "job_preview"}),
        timezone="Asia/Kolkata",
    )
    assert (await anonymous.post(f"{INSTALLS}/events", json=sent)).status_code == 204
    automated = batch(bot, event("job_detected"), automated=True)
    assert (await anonymous.post(f"{INSTALLS}/events", json=automated)).status_code == 204
    before = batch(connected, event("job_detected"))
    assert (await anonymous.post(f"{INSTALLS}/events", json=before)).status_code == 204
    client.headers["x-test-extension"] = "1"
    linked = {"events": [event("popup_opened")], "install": connected}
    assert (await client.post(EVENTS, json=linked)).status_code == 204

    stats = (await admin.get(f"{ADMIN}/ext-installs?hours=1")).json()["without_account"]
    rows = {row["install_id"]: row for row in stats["rows"]}
    assert set(rows) & {using, bot, connected} == {using}
    row = rows[using]
    assert (row["job_pages"], row["previews"], row["setup_opens"]) == (1, 1, 1)
    assert row["timezone"] == "Asia/Kolkata" and row["days_active"] == 1
    assert stats["active"] >= 1 and stats["saw_preview"] >= 1 and stats["opened_setup"] >= 1
    assert stats["active_with_account"] >= 1


@pytest.mark.parametrize("path", ["/ext-installs", f"/ext-installs/{uuid.uuid4()}/events"])
async def test_an_ordinary_user_cannot_read_installs(client: AsyncClient, path: str) -> None:
    assert (await client.get(f"{ADMIN}{path}")).status_code == 403
