import base64
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from backend.core import storage
from backend.tests.conftest import ClientFactory

BASE = "/api/v1/resume-editor"
JAKE = (Path(__file__).parent / "fixtures" / "resumes" / "jake.pdf").read_bytes()


@pytest.fixture(autouse=True)
def bucket(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    """An in-memory stand-in for R2, so tests never touch real storage."""
    files: dict[str, bytes] = {}

    async def put_file(key: str, data: bytes, *, content_type: str) -> None:
        files[key] = data

    async def get_file(key: str) -> bytes:
        return files[key]

    async def delete_file(key: str) -> None:
        files.pop(key, None)

    monkeypatch.setattr(storage, "put_file", put_file)
    monkeypatch.setattr(storage, "get_file", get_file)
    monkeypatch.setattr(storage, "delete_file", delete_file)
    return files


async def _upload(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/resume", files={"file": ("resume.pdf", JAKE, "application/pdf")}
    )
    assert response.status_code == 201, response.text


def _line(layout: dict[str, Any], starts: str) -> dict[str, Any]:
    return next(
        line
        for section in layout["sections"]
        for line in section["lines"]
        if line["text"].startswith(starts)
    )


async def test_opens_the_resume_as_sections(client: AsyncClient) -> None:
    await _upload(client)
    response = await client.get(BASE)
    assert response.status_code == 200, response.text
    layout = response.json()
    assert [section["title"] for section in layout["sections"]][:3] == [
        "Header",
        "Education",
        "Experience",
    ]
    assert [section["is_skills"] for section in layout["sections"]][-1] is True
    assert layout["skill_rows"] == ["Languages", "Frameworks", "Developer Tools"]
    assert len(layout["pages"]) == 1
    assert base64.b64decode(layout["pages"][0]["image"]).startswith(b"\x89PNG")
    bullet = _line(layout, "Mentored")
    assert bullet["bullet"] and bullet["can_add_below"]


async def test_preview_changes_nothing_and_save_replaces_the_resume(
    client: AsyncClient, bucket: dict[str, bytes]
) -> None:
    await _upload(client)
    layout = (await client.get(BASE)).json()
    original_key = next(iter(bucket))
    body = {
        "resume_id": layout["resume_id"],
        "edits": [
            {"kind": "change", "line_id": _line(layout, "Razorpay")["id"], "text": "Razorpay Inc"},
            {"kind": "remove", "line_id": _line(layout, "Reduced p99")["id"]},
            {"kind": "add_below", "line_id": _line(layout, "Mentored")["id"], "text": "Ran oncall"},
        ],
        "skills": [{"name": "Kotlin"}],
    }

    preview = await client.post(f"{BASE}/preview", json=body)
    assert preview.status_code == 200, preview.text
    edited = preview.json()
    assert [outcome["applied"] for outcome in edited["outcomes"]] == [True, True, True]
    assert [item["skill"] for item in edited["added"]] == ["Kotlin"]
    assert base64.b64decode(edited["pdf"]).startswith(b"%PDF")
    # A preview stores nothing.
    assert list(bucket) == [original_key] and bucket[original_key] == JAKE

    saved = await client.post(f"{BASE}/save", json=body)
    assert saved.status_code == 200, saved.text
    assert original_key not in bucket
    profile = (await client.get("/api/v1/profile/me")).json()
    assert "Kotlin" in [skill["name"] for skill in profile["skills"]]

    # The editor now opens the new file, and the old id is refused.
    reopened = (await client.get(BASE)).json()
    assert reopened["resume_id"] == saved.json()["id"]
    assert _line(reopened, "Razorpay")["text"] == "Razorpay Inc"
    stale = await client.post(f"{BASE}/preview", json=body)
    assert stale.status_code == 409


async def test_clear_errors(client: AsyncClient) -> None:
    missing = await client.get(BASE)
    assert missing.status_code == 404
    assert "Upload your resume" in missing.json()["detail"]

    await _upload(client)
    layout = (await client.get(BASE)).json()
    empty = await client.post(f"{BASE}/preview", json={"resume_id": layout["resume_id"]})
    assert empty.status_code == 422

    too_long = "Software Development Engineer II, Platform Lead for Payments and Refunds " * 2
    line = _line(layout, "Software Development")["id"]
    body = {
        "resume_id": layout["resume_id"],
        "edits": [{"kind": "change", "line_id": line, "text": too_long}],
    }
    preview = (await client.post(f"{BASE}/preview", json=body)).json()
    assert preview["outcomes"][0]["applied"] is False
    assert "too long" in preview["outcomes"][0]["message"]
    nothing = await client.post(f"{BASE}/save", json=body)
    assert nothing.status_code == 422


async def test_each_user_edits_only_their_own_resume(make_client: ClientFactory) -> None:
    first, second = make_client(), make_client()
    await _upload(first)
    layout = (await first.get(BASE)).json()
    body = {
        "resume_id": layout["resume_id"],
        "edits": [{"kind": "remove", "line_id": _line(layout, "Reduced p99")["id"]}],
    }

    # The second user has no resume, and cannot reach the first user's by its id.
    assert (await second.get(BASE)).status_code == 404
    assert (await second.post(f"{BASE}/preview", json=body)).status_code == 404
    assert (await second.post(f"{BASE}/save", json=body)).status_code == 404
    assert (await first.post(f"{BASE}/preview", json=body)).status_code == 200
