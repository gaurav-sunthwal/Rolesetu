from pathlib import Path

import pytest
from httpx import AsyncClient

from backend.core import storage
from backend.tests.conftest import ClientFactory

BASE = "/api/v1/resume"
FIXTURES = Path(__file__).parent / "fixtures" / "resumes"
CLASSIC = (FIXTURES / "classic.pdf").read_bytes()
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

    async def signed_download_url(key: str, *, filename: str, expires_in: int = 300) -> str:
        return f"https://signed.example/{key}?expires={expires_in}"

    monkeypatch.setattr(storage, "put_file", put_file)
    monkeypatch.setattr(storage, "get_file", get_file)
    monkeypatch.setattr(storage, "delete_file", delete_file)
    monkeypatch.setattr(storage, "signed_download_url", signed_download_url)
    return files


async def _upload(client: AsyncClient, data: bytes, name: str = "resume.pdf") -> dict:  # type: ignore[type-arg]
    response = await client.post(BASE, files={"file": (name, data, "application/pdf")})
    assert response.status_code == 201, response.text
    body: dict = response.json()  # type: ignore[type-arg]
    return body


async def test_upload_is_parsed_and_fills_an_empty_profile(
    client: AsyncClient, bucket: dict[str, bytes]
) -> None:
    started = await _upload(client, CLASSIC, "Asha Rao CV.pdf")
    assert started["status"] == "parsed"
    assert len(bucket) == 1

    resume = (await client.get(f"{BASE}/{started['id']}")).json()
    assert resume["filename"] == "Asha Rao CV.pdf"
    assert resume["parsed"]["full_name"] == "Asha Rao"
    assert len(resume["parsed"]["experience"]) == 2

    applied = await client.post(f"{BASE}/{started['id']}/apply", json={"mode": "merge"})
    assert applied.status_code == 200
    profile = applied.json()["profile"]
    assert profile["full_name"] == "Asha Rao"
    assert len(profile["skills"]) == 14
    # name 10 + headline 10 + 5+ skills 20 + experience 25 + projects 15 + education 10 + link 10
    assert profile["completeness"] == 100
    assert applied.json()["resume"]["applied_at"] is not None

    saved = (await client.get("/api/v1/profile/me")).json()
    assert saved["experience"][0]["company"] == "Phenko Technologies Pvt. Ltd."


async def test_merge_does_not_overwrite_and_replace_does(client: AsyncClient) -> None:
    await client.put("/api/v1/profile/me", json={"full_name": "My Own Name", "headline": "Mine"})
    resume = await _upload(client, CLASSIC)

    merged = await client.post(f"{BASE}/{resume['id']}/apply", json={"mode": "merge"})
    assert merged.json()["profile"]["full_name"] == "My Own Name"
    assert len(merged.json()["profile"]["experience"]) == 2

    # Applying the same resume twice must not duplicate anything.
    again = await client.post(f"{BASE}/{resume['id']}/apply", json={"mode": "merge"})
    assert len(again.json()["profile"]["experience"]) == 2
    assert len(again.json()["profile"]["skills"]) == 14

    replaced = await client.post(f"{BASE}/{resume['id']}/apply", json={"mode": "replace"})
    assert replaced.json()["profile"]["full_name"] == "Asha Rao"


async def test_a_new_upload_replaces_the_previous_file(
    client: AsyncClient, bucket: dict[str, bytes]
) -> None:
    first = await _upload(client, CLASSIC)
    second = await _upload(client, TWOCOL)
    assert len(bucket) == 1
    assert (await client.get(f"{BASE}/{first['id']}")).status_code == 404
    latest = (await client.get(f"{BASE}/latest")).json()
    assert latest["id"] == second["id"]
    assert latest["parsed"]["full_name"] == "Rahul Verma"


async def test_latest_is_null_before_any_upload(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/latest")
    assert response.status_code == 200 and response.json() is None


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"PK\x03\x04 this is a docx, not a pdf", "not a PDF"),
        (b"", "empty"),
        (b"%PDF-1.4" + b"0" * (5 * 1024 * 1024 + 1), "larger than 5 MB"),
    ],
)
async def test_bad_files_are_rejected_and_not_stored(
    client: AsyncClient, bucket: dict[str, bytes], data: bytes, message: str
) -> None:
    response = await client.post(BASE, files={"file": ("resume.pdf", data, "application/pdf")})
    assert response.status_code == 422
    assert message in response.json()["detail"]
    assert bucket == {}


async def test_scanned_pdf_is_rejected_and_not_stored(
    client: AsyncClient, bucket: dict[str, bytes]
) -> None:
    blank = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF"
    )
    response = await client.post(BASE, files={"file": ("scan.pdf", blank, "application/pdf")})
    assert response.status_code == 422
    assert "scan" in response.json()["detail"]
    assert bucket == {}
    assert (await client.get(f"{BASE}/latest")).json() is None


async def test_a_failed_upload_keeps_the_resume_already_on_file(
    client: AsyncClient, bucket: dict[str, bytes]
) -> None:
    good = await _upload(client, CLASSIC)
    bad = await client.post(BASE, files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert bad.status_code == 422
    assert (await client.get(f"{BASE}/latest")).json()["id"] == good["id"]
    assert len(bucket) == 1


async def test_download_link_and_delete(client: AsyncClient, bucket: dict[str, bytes]) -> None:
    resume = await _upload(client, CLASSIC)
    link = (await client.get(f"{BASE}/{resume['id']}/download-link")).json()
    assert link["url"].startswith("https://signed.example/resumes/") and link["expires_in"] == 300

    assert (await client.delete(f"{BASE}/{resume['id']}")).status_code == 204
    assert bucket == {}
    assert (await client.get(f"{BASE}/latest")).json() is None


async def test_resumes_are_private_to_their_owner(make_client: ClientFactory) -> None:
    alice, bob = make_client(), make_client()
    resume = await _upload(alice, CLASSIC)
    url = f"{BASE}/{resume['id']}"

    assert (await bob.get(url)).status_code == 404
    assert (await bob.get(f"{url}/download-link")).status_code == 404
    assert (await bob.post(f"{url}/apply", json={"mode": "replace"})).status_code == 404
    assert (await bob.delete(url)).status_code == 404
    assert (await bob.get(f"{BASE}/latest")).json() is None
    assert (await bob.get("/api/v1/profile/me")).json()["full_name"] is None
