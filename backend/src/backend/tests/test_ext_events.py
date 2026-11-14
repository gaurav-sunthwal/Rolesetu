"""Extension usage analytics: what the extension may send, how it is stored, and
what the admin panel reads back."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from backend.core.config import get_settings
from backend.modules.ext_events.schemas import ExtEventWrite
from backend.tests.conftest import ClientFactory

EVENTS = "/api/v1/extension/events"
ADMIN = "/api/v1/admin"


def event(name: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "id": str(uuid.uuid4()), "version": "1.3.0", **extra}


# ── What the extension may send (no database) ─────────────────────────────────


def test_an_event_carries_short_labels_only() -> None:
    sent = ExtEventWrite.model_validate(
        event("ai_failed", host="wellfound.com", props={"mode": "write", "reason": "limit"})
    )
    assert sent.props == {"mode": "write", "reason": "limit"}

    with pytest.raises(ValidationError):  # too many labels
        ExtEventWrite.model_validate(event("ai_failed", props={f"k{i}": 1 for i in range(7)}))
    with pytest.raises(ValidationError):  # a label name that is not a plain word
        ExtEventWrite.model_validate(event("ai_failed", props={"Bad Key": 1}))
    with pytest.raises(ValidationError):  # long text, as typed text would be
        ExtEventWrite.model_validate(event("ai_failed", props={"note": "x" * 61}))
    with pytest.raises(ValidationError):  # a name the server does not know
        ExtEventWrite.model_validate(event("keystroke_logged"))


def test_an_events_own_time_is_kept_only_when_believable() -> None:
    now = datetime.now(UTC)
    held_back = ExtEventWrite.model_validate(
        event("extension_installed", at=now - timedelta(days=2))
    )
    assert held_back.happened_at(now) == now - timedelta(days=2)
    future = ExtEventWrite.model_validate(event("extension_installed", at=now + timedelta(days=1)))
    assert future.happened_at(now) is None
    ancient = ExtEventWrite.model_validate(
        event("extension_installed", at=now - timedelta(days=30))
    )
    assert ancient.happened_at(now) is None


@pytest.mark.parametrize("path", ["/ext-analytics", f"/users/{uuid.uuid4()}/ext-events"])
async def test_an_ordinary_user_cannot_read_analytics(client: AsyncClient, path: str) -> None:
    assert (await client.get(f"{ADMIN}{path}")).status_code == 403


# ── Stored and read back (needs migration b8d2e4f6a1c3 applied) ──────────────


@pytest.fixture
async def admin(make_client: ClientFactory, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    client = make_client()
    client.headers["x-test-verified"] = "1"
    monkeypatch.setattr(
        get_settings(), "admin_emails", [f"{client.headers['x-test-uid']}@example.com"]
    )
    return client


async def test_a_retried_batch_is_stored_once(client: AsyncClient, admin: AsyncClient) -> None:
    batch = {"events": [event("autofill_filled", host="wellfound.com", count=4)]}
    assert (await client.post(EVENTS, json=batch)).status_code == 204
    assert (await client.post(EVENTS, json=batch)).status_code == 204

    stats = (await admin.get(f"{ADMIN}/ext-analytics?hours=1")).json()
    filled = next(row for row in stats["features"] if row["name"] == "autofill_filled")
    assert filled["events"] >= 1
    site = next(row for row in stats["sites"] if row["host"] == "wellfound.com")
    assert site["filled"] == filled["events"]


async def test_the_admin_page_reads_the_funnel_ai_and_errors(
    client: AsyncClient, admin: AsyncClient
) -> None:
    batch = {
        "events": [
            event("form_detected", host="wellfound.com"),
            event("autofill_offered", host="wellfound.com", count=3),
            event("autofill_filled", host="wellfound.com", count=3),
            event("ai_requested", props={"mode": "write"}),
            event("ai_failed", props={"mode": "write", "reason": "limit"}),
            event("ext_error", props={"where": "content", "kind": "TypeError"}),
        ]
    }
    assert (await client.post(EVENTS, json=batch)).status_code == 204
    stats = (await admin.get(f"{ADMIN}/ext-analytics?hours=1")).json()

    steps = {step["step"]: step for step in stats["funnel"]}
    assert steps["form_detected"]["users"] >= 1 and steps["autofill_filled"]["users"] >= 1
    assert stats["ai"]["limit_hits"] >= 1
    assert any(row["label"] == "write" for row in stats["ai"]["by_mode"])
    assert any(row["where"] == "content" and row["version"] == "1.3.0" for row in stats["errors"])
    assert any(row["version"] == "1.3.0" for row in stats["versions"])
    assert stats["overview"]["active_1d"] >= 1
