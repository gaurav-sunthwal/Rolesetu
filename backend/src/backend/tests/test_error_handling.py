"""Whatever goes wrong, the reply is JSON with a sentence a person can act on.

Clients show `detail` as it is. A list of error objects, a bare "Internal
Server Error" page or a stack trace would leave them with nothing to show.
"""

from pathlib import Path

import pytest
from httpx import AsyncClient

from backend.core import storage
from backend.core.exceptions import describe_validation
from backend.modules.tailoring.pdf import editor

FIXTURES = Path(__file__).parent / "fixtures" / "resumes"
JAKE = (FIXTURES / "jake.pdf").read_bytes()


def test_refused_requests_are_explained_in_words() -> None:
    too_long = {
        "type": "string_too_long",
        "loc": ("body", "skills", 0, "name"),
        "msg": "String should have at most 60 characters",
        "ctx": {"max_length": 60},
    }
    assert describe_validation([too_long]) == "A skill name is too long (the limit is 60)."

    too_short = {"type": "string_too_short", "loc": ("body", "jd_text"), "ctx": {"min_length": 200}}
    assert describe_validation([too_short]) == (
        "The job description is too short (it needs at least 200)."
    )
    ours = {"type": "value_error", "loc": ("body",), "msg": "Value error, Choose at least one."}
    assert describe_validation([ours]) == "Choose at least one."
    assert describe_validation([{"type": "missing", "loc": ("body", "file")}]) == (
        "The file is missing."
    )
    # Something we have no words for still gets a sentence, never a raw object.
    odd = describe_validation([{"type": "weird", "loc": ("query", "zzz"), "msg": "?"}])
    assert odd == "Part of that request is not valid. Please check it and try again."
    assert describe_validation([]).endswith("Please try again.")


@pytest.fixture
def bucket(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
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


async def test_every_failure_is_json_with_a_sentence(
    client: AsyncClient, bucket: dict[str, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    # A request outside the limits: one sentence, not a list of objects.
    short = await client.post("/api/v1/matches", json={"jd_text": "too short"})
    assert short.status_code == 422
    assert short.json() == {"detail": "The job description is too short (it needs at least 200)."}

    nothing = await client.post("/api/v1/tailored-resumes", json={"skills": []})
    assert nothing.json() == {"detail": "Choose at least one change to make."}

    long_name = (
        "JavaScript or TypeScript or Python or C or C# or C++ or React or Go or Rust or Java"
    )
    refused = await client.post("/api/v1/tailored-resumes", json={"skills": [{"name": long_name}]})
    assert refused.status_code == 422
    assert refused.json() == {"detail": "A skill name is too long (the limit is 60)."}

    upload = await client.post(
        "/api/v1/resume", files={"file": ("resume.pdf", JAKE, "application/pdf")}
    )
    assert upload.status_code == 201

    # The PDF editor failing in a way nobody planned for: the user is told their
    # resume is untouched, and is not shown the error itself.
    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("xref table is corrupt at offset 4821")

    monkeypatch.setattr(editor, "tailor", explode)
    broken = await client.post("/api/v1/tailored-resumes", json={"skills": [{"name": "Kotlin"}]})
    assert broken.status_code == 422
    detail = broken.json()["detail"]
    assert "Your resume has not been changed" in detail
    assert "xref" not in detail
    assert bucket[next(iter(bucket))] == JAKE

    kept = await client.post("/api/v1/tailored-resumes/keep", json={"skills": [{"name": "Kotlin"}]})
    assert kept.status_code == 422
    assert bucket[next(iter(bucket))] == JAKE  # nothing was saved over the original


async def test_a_bug_is_reported_as_json_without_internals(
    make_client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from httpx import ASGITransport

    from backend.main import app
    from backend.modules.profiles import service as profiles_service

    async def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("connection pool exhausted: secret-host.internal:5432")

    monkeypatch.setattr(profiles_service, "get_profile", explode)
    client = make_client()  # type: ignore[operator]
    # Let the error reach the app's own handler instead of the test raising it.
    client._transport = ASGITransport(app=app, raise_app_exceptions=False)
    response = await client.get("/api/v1/profile/me")
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    detail = response.json()["detail"]
    assert detail.startswith("Something went wrong on our side")
    assert "secret-host" not in detail and "pool" not in detail
