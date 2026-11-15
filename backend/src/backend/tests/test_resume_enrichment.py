"""A resume is read by code and answered at once; the AI's understanding (field,
headline, more skills) is added afterwards, without replacing anything the person
has on their profile. Through the API and database, with the AI faked."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from backend.ai.profile_understanding import CategorizedSkills, ProfileUnderstanding
from backend.core import storage
from backend.db.session import get_sessionmaker
from backend.modules.profiles.schemas import ProfileWrite, SkillItem
from backend.modules.resumes import service
from backend.modules.resumes.models import ResumeFile
from backend.tests.test_resumes_api import BASE, CLASSIC

UNDERSTOOD = ProfileUnderstanding(
    headline="Backend engineer, payments",
    field="software",
    scope_summary="Builds payment APIs.",
    categorized_skills=CategorizedSkills(technical_software=["Kafka", "Terraform"]),
    skills=["Distributed systems", "kafka"],
)


@pytest.fixture
def files(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    """Resume files kept in memory instead of R2."""
    kept: dict[str, bytes] = {}

    async def put_file(key: str, data: bytes, *, content_type: str) -> None:
        kept[key] = data

    async def delete_file(key: str) -> None:
        kept.pop(key, None)

    monkeypatch.setattr(storage, "put_file", put_file)
    monkeypatch.setattr(storage, "delete_file", delete_file)
    return kept


def fake_ai(answer: ProfileUnderstanding | None) -> Any:
    async def understand(*_: object, **__: object) -> ProfileUnderstanding | None:
        return answer

    return understand


def test_the_ai_only_adds_never_replaces() -> None:
    mine = ProfileWrite(
        headline="My own headline",
        skills=[SkillItem(id="a", name="Kafka"), SkillItem(id="b", name="Python")],
    )
    merged = service.add_understanding(mine, UNDERSTOOD)
    assert merged.headline == "My own headline"
    names = [skill.name for skill in merged.skills]
    assert names[:2] == ["Kafka", "Python"]
    assert names.count("Kafka") == 1 and "kafka" not in names  # no duplicates, any case
    assert "Terraform" in names and "Distributed systems" in names
    # The original is left as it was.
    assert [skill.name for skill in mine.skills] == ["Kafka", "Python"]


@pytest.mark.real_resume_ai
async def test_upload_answers_with_the_resume_and_the_ai_fills_in_after(
    client: AsyncClient, files: dict[str, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "understand_profile", fake_ai(UNDERSTOOD))
    uploaded = await client.post(BASE, files={"file": ("cv.pdf", CLASSIC, "application/pdf")})
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    # The answer is what code read: the AI had not run yet.
    assert body["ai_status"] == "pending"
    assert "Terraform" not in [skill["name"] for skill in body["parsed"]["skills"]]

    # It ran after the answer: the resume now carries its understanding.
    latest = (await client.get(f"{BASE}/latest")).json()
    assert latest["ai_status"] == "done"
    assert "Terraform" in [skill["name"] for skill in latest["parsed"]["skills"]]

    applied = await client.post(f"{BASE}/{body['id']}/apply", json={"mode": "merge"})
    assert applied.status_code == 200, applied.text
    profile = (await client.get("/api/v1/profile/me")).json()
    assert "Terraform" in [skill["name"] for skill in profile["skills"]]


@pytest.mark.real_resume_ai
async def test_an_ai_that_finishes_after_the_profile_is_filled_adds_to_it(
    client: AsyncClient, files: dict[str, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "understand_profile", fake_ai(None))
    uploaded = (
        await client.post(BASE, files={"file": ("cv.pdf", CLASSIC, "application/pdf")})
    ).json()
    await client.post(f"{BASE}/{uploaded['id']}/apply", json={"mode": "merge"})
    # The person edits their headline before the AI is back.
    profile = (await client.get("/api/v1/profile/me")).json()
    profile["headline"] = "Typed by me"
    keep = {k: v for k, v in profile.items() if k not in ("version", "completeness", "updated_at")}
    assert (await client.put("/api/v1/profile/me", json=keep)).status_code == 200

    # Now the AI finishes (as a slow model would, after the profile was filled).
    async with get_sessionmaker()() as db:
        await db.execute(
            update(ResumeFile)
            .where(ResumeFile.id == uuid.UUID(uploaded["id"]))
            .values(ai_status="pending")
        )
        await db.commit()
    user_id = uuid.UUID((await client.get("/api/v1/users/me")).json()["id"])
    monkeypatch.setattr(service, "understand_profile", fake_ai(UNDERSTOOD))
    await service.enrich_in_background(uuid.UUID(uploaded["id"]), user_id, "resume text")

    after = (await client.get("/api/v1/profile/me")).json()
    assert after["headline"] == "Typed by me"
    assert "Terraform" in [skill["name"] for skill in after["skills"]]
    assert (await client.get(f"{BASE}/latest")).json()["ai_status"] == "done"


@pytest.mark.real_resume_ai
async def test_when_the_ai_is_unavailable_the_profile_still_works(
    client: AsyncClient, files: dict[str, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "understand_profile", fake_ai(None))
    uploaded = await client.post(BASE, files={"file": ("cv.pdf", CLASSIC, "application/pdf")})
    assert uploaded.status_code == 201
    assert len(uploaded.json()["parsed"]["skills"]) > 0
    assert (await client.get(f"{BASE}/latest")).json()["ai_status"] == "failed"


@pytest.mark.real_resume_ai
async def test_one_request_uploads_and_fills_the_profile(
    client: AsyncClient, files: dict[str, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "understand_profile", fake_ai(UNDERSTOOD))
    response = await client.post(
        f"{BASE}/fill", files={"file": ("cv.pdf", CLASSIC, "application/pdf")}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["resume"]["applied_at"] is not None
    assert len(body["profile"]["skills"]) > 0
    assert len(files) == 1  # the PDF was stored
    # The AI ran after the answer and added to the filled profile.
    profile = (await client.get("/api/v1/profile/me")).json()
    assert "Terraform" in [skill["name"] for skill in profile["skills"]]
