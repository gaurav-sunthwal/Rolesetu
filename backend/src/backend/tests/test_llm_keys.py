from typing import Any

import pytest
from google import genai
from google.genai import errors
from httpx import AsyncClient

from backend.ai.llm_client import (
    InvalidLLMKeyError,
    LLMKeyCheckUnavailableError,
    LLMKeyQuotaError,
    verify_api_key,
)
from backend.modules.llm_keys import service
from backend.tests.conftest import ClientFactory

GOOD_KEY = "good-key-1234567890"
BAD_KEY = "bad-key-1234567890"


@pytest.fixture
def key_check(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Stands in for the Gemini call: GOOD_KEY passes, anything else is rejected."""
    seen: list[str] = []

    async def fake_verify(key: str) -> None:
        seen.append(key)
        if key != GOOD_KEY:
            raise InvalidLLMKeyError()

    monkeypatch.setattr(service, "verify_api_key", fake_verify)
    return seen


async def test_working_key_is_tested_then_saved(client: AsyncClient, key_check: list[str]) -> None:
    response = await client.put("/api/v1/llm-keys/me", json={"api_key": f"  {GOOD_KEY}\n"})

    assert response.status_code == 200
    assert response.json()["has_key"] is True
    assert key_check == [GOOD_KEY]
    assert (await client.get("/api/v1/llm-keys/me")).json()["has_key"] is True


async def test_rejected_key_is_not_saved(client: AsyncClient, key_check: list[str]) -> None:
    response = await client.put("/api/v1/llm-keys/me", json={"api_key": BAD_KEY})

    assert response.status_code == 422
    assert "rejected this API key" in response.json()["detail"]
    assert BAD_KEY not in response.text
    assert (await client.get("/api/v1/llm-keys/me")).json()["has_key"] is False


async def test_rejected_replacement_keeps_the_existing_key(
    client: AsyncClient, key_check: list[str]
) -> None:
    saved = (await client.put("/api/v1/llm-keys/me", json={"api_key": GOOD_KEY})).json()

    response = await client.put("/api/v1/llm-keys/me", json={"api_key": BAD_KEY})

    assert response.status_code == 422
    assert (await client.get("/api/v1/llm-keys/me")).json() == saved


async def test_key_is_not_saved_when_google_cannot_be_reached(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def unreachable(key: str) -> None:
        raise LLMKeyCheckUnavailableError()

    monkeypatch.setattr(service, "verify_api_key", unreachable)

    response = await client.put("/api/v1/llm-keys/me", json={"api_key": GOOD_KEY})

    assert response.status_code == 503
    assert (await client.get("/api/v1/llm-keys/me")).json()["has_key"] is False


async def test_key_status_is_private_to_its_owner(
    make_client: ClientFactory, key_check: list[str]
) -> None:
    owner, stranger = make_client(), make_client()
    await owner.put("/api/v1/llm-keys/me", json={"api_key": GOOD_KEY})

    assert (await stranger.get("/api/v1/llm-keys/me")).json()["has_key"] is False
    assert (await stranger.delete("/api/v1/llm-keys/me")).status_code == 204
    assert (await owner.get("/api/v1/llm-keys/me")).json()["has_key"] is True


class _FakeModels:
    def __init__(self, outcome: Exception | None) -> None:
        self._outcome = outcome

    async def generate_content(self, **_: Any) -> object:
        if self._outcome is not None:
            raise self._outcome
        return object()


class _FakeGenaiClient:
    def __init__(self, outcome: Exception | None) -> None:
        self.aio = type("Aio", (), {"models": _FakeModels(outcome)})()


def _gemini_answers(monkeypatch: pytest.MonkeyPatch, outcome: Exception | None) -> None:
    monkeypatch.setattr(genai, "Client", lambda api_key: _FakeGenaiClient(outcome))


def _api_error(kind: type[errors.APIError], code: int) -> errors.APIError:
    return kind(code, {"error": {"code": code, "message": "nope", "status": "ERROR"}})


async def test_verify_passes_when_gemini_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    _gemini_answers(monkeypatch, None)

    await verify_api_key(GOOD_KEY)


@pytest.mark.parametrize("code", [400, 401, 403])
async def test_verify_reports_a_rejected_key(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    _gemini_answers(monkeypatch, _api_error(errors.ClientError, code))

    with pytest.raises(InvalidLLMKeyError):
        await verify_api_key(BAD_KEY)


async def test_verify_reports_exhausted_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    _gemini_answers(monkeypatch, _api_error(errors.ClientError, 429))

    with pytest.raises(LLMKeyQuotaError):
        await verify_api_key(GOOD_KEY)


@pytest.mark.parametrize(
    "outcome",
    [_api_error(errors.ServerError, 503), TimeoutError(), _api_error(errors.ClientError, 404)],
)
async def test_verify_does_not_blame_the_key_for_outages(
    monkeypatch: pytest.MonkeyPatch, outcome: Exception
) -> None:
    _gemini_answers(monkeypatch, outcome)

    with pytest.raises(LLMKeyCheckUnavailableError):
        await verify_api_key(GOOD_KEY)
