import base64
from pathlib import Path

import pytest
from httpx import AsyncClient

from backend.core import storage
from backend.tests.conftest import ClientFactory

BASE = "/api/v1/tailored-resumes"
FIXTURES = Path(__file__).parent / "fixtures" / "resumes"
JAKE = (FIXTURES / "jake.pdf").read_bytes()
TWOCOL = (FIXTURES / "twocol.pdf").read_bytes()


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


async def _upload(client: AsyncClient, data: bytes) -> None:
    response = await client.post(
        "/api/v1/resume", files={"file": ("resume.pdf", data, "application/pdf")}
    )
    assert response.status_code == 201, response.text


async def _upload_to_profile(client: AsyncClient, data: bytes) -> None:
    """Uploads a resume and puts what it says on the profile, as a job check needs."""
    uploaded = await client.post(
        "/api/v1/resume", files={"file": ("resume.pdf", data, "application/pdf")}
    )
    applied = await client.post(
        f"/api/v1/resume/{uploaded.json()['id']}/apply", json={"mode": "merge"}
    )
    assert applied.status_code == 200, applied.text


async def test_adds_skills_keeps_the_original_and_updates_the_profile(
    client: AsyncClient, bucket: dict[str, bytes]
) -> None:
    await _upload(client, JAKE)
    original_key = next(iter(bucket))

    response = await client.post(
        BASE, json={"skills": [{"name": "Kotlin"}, {"name": "Docker"}, {"name": "Terraform"}]}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [(item["skill"], item["row"]) for item in body["added"]] == [
        ("Kotlin", "Languages"),
        ("Terraform", "Developer Tools"),
    ]
    assert all(item["readable"] for item in body["added"])
    assert [(item["skill"], item["reason"]) for item in body["skipped"]] == [
        ("Docker", "already_listed")
    ]
    assert body["rows"] == ["Languages", "Frameworks", "Developer Tools"]
    assert len(body["before"]) == len(body["after"]) == 1
    assert body["filename"] == "resume.pdf"

    # The copy comes back in the response and is a different file from the original.
    copy = base64.b64decode(body["pdf"])
    assert copy.startswith(b"%PDF-") and copy != JAKE
    assert base64.b64decode(body["after"][0]).startswith(b"\x89PNG")

    # Nothing new is stored, and the uploaded file is untouched.
    assert bucket == {original_key: JAKE}

    # A preview changes nothing: the profile does not gain the skills yet.
    profile = (await client.get("/api/v1/profile/me")).json()
    assert "Kotlin" not in {skill["name"] for skill in profile["skills"]}


async def test_keeping_the_copy_updates_resume_and_profile_together(
    client: AsyncClient, bucket: dict[str, bytes]
) -> None:
    await _upload(client, JAKE)
    changes = {"skills": [{"name": "Kotlin"}, {"name": "Docker"}]}

    kept = await client.post(f"{BASE}/keep", json=changes)
    assert kept.status_code == 200, kept.text
    # Docker was already on the resume, so only Kotlin counts as added.
    assert kept.json() == {"filename": "resume.pdf", "skills_added": ["Kotlin"]}

    # The saved resume is now the updated file (and the only one stored).
    assert len(bucket) == 1
    saved = next(iter(bucket.values()))
    assert saved != JAKE and b"%PDF-" in saved[:8]
    profile = (await client.get("/api/v1/profile/me")).json()
    assert "Kotlin" in {skill["name"] for skill in profile["skills"]}

    # Asking for the same skill again finds it on the resume this time.
    again = await client.post(BASE, json={"skills": [{"name": "Kotlin"}]})
    assert again.status_code == 422
    assert "Already in your Skills section" in again.json()["detail"]


async def test_the_user_can_move_a_skill_to_another_row(client: AsyncClient) -> None:
    await _upload(client, JAKE)
    response = await client.post(
        BASE, json={"skills": [{"name": "Kotlin", "row": "Developer Tools"}]}
    )
    assert response.json()["added"][0]["row"] == "Developer Tools"


async def test_clear_errors_when_it_cannot_be_done(client: AsyncClient) -> None:
    no_resume = await client.post(BASE, json={"skills": [{"name": "Kotlin"}]})
    assert no_resume.status_code == 404
    assert "Upload your resume" in no_resume.json()["detail"]

    await _upload(client, TWOCOL)
    one_per_line = await client.post(BASE, json={"skills": [{"name": "Celery"}]})
    assert one_per_line.status_code == 422
    assert "one skill per line" in one_per_line.json()["detail"]

    await _upload(client, JAKE)
    nothing_new = await client.post(BASE, json={"skills": [{"name": "Docker"}]})
    assert nothing_new.status_code == 422
    assert "Already in your Skills section" in nothing_new.json()["detail"]

    assert (await client.post(BASE, json={"skills": []})).status_code == 422


async def test_each_user_gets_their_own_resume(make_client: ClientFactory) -> None:
    first, second = make_client(), make_client()
    await _upload(first, JAKE)

    # The second user has no resume of their own, and never gets the first user's.
    assert (await second.post(BASE, json={"skills": [{"name": "Kotlin"}]})).status_code == 404
    assert (await first.post(BASE, json={"skills": [{"name": "Kotlin"}]})).status_code == 200


CLASSIC = (FIXTURES / "classic.pdf").read_bytes()
JOB = """Sr. Frontend Developer - Bengaluru

About the role: we are looking for a frontend developer to build the web app our customers
use every day, working closely with design and backend teams.

Requirements:
- 3+ years with React and TypeScript
- Experience with GraphQL and Kubernetes
- Strong JavaScript fundamentals

Nice to have: Figma"""


async def test_keyword_check_and_rewording(client: AsyncClient, bucket: dict[str, bytes]) -> None:
    await _upload_to_profile(client, CLASSIC)
    match = await client.post(
        "/api/v1/matches",
        json={"jd_text": JOB, "role": "Sr. Frontend Developer - Bengaluru", "company": "Acme"},
    )
    assert match.is_success, match.text

    check = await client.get(f"{BASE}/keywords", params={"match_id": match.json()["id"]})
    assert check.status_code == 200, check.text
    body = check.json()
    # "Sr." is dropped: the resume's headline claims no seniority.
    assert body["title"] == {
        "wanted": "Sr. Frontend Developer",
        "present": False,
        "current": "Frontend Engineer",
        "suggested": "Frontend Developer",
    }
    status = {skill["name"]: skill["status"] for skill in body["skills"]}
    assert status["React"] == "present"
    assert status["GraphQL"] == "missing"

    tailored = await client.post(
        BASE, json={"headline": "Frontend Developer", "skills": [{"name": "GraphQL"}]}
    )
    assert tailored.status_code == 200, tailored.text
    result = tailored.json()
    assert result["changes"] == [
        {
            "kind": "headline",
            "before": "Frontend Engineer",
            "after": "Frontend Developer",
            "applied": True,
            "message": None,
            "exact_font": result["changes"][0]["exact_font"],
        }
    ]
    assert [item["skill"] for item in result["added"]] == ["GraphQL"]
    assert len(bucket) == 1  # still only the uploaded resume

    assert (await client.post(BASE, json={})).status_code == 422


async def test_keyword_check_is_scoped_to_the_user(make_client: ClientFactory) -> None:
    owner, stranger = make_client(), make_client()
    await _upload_to_profile(owner, CLASSIC)
    await _upload(stranger, CLASSIC)
    match = await owner.post("/api/v1/matches", json={"jd_text": JOB, "role": "Frontend Developer"})
    params = {"match_id": match.json()["id"]}

    assert (await owner.get(f"{BASE}/keywords", params=params)).status_code == 200
    assert (await stranger.get(f"{BASE}/keywords", params=params)).status_code == 404
