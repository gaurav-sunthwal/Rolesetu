"""Users' own Gemini keys are retired (ADR 13): none can be saved, none is used,
and one saved before can still be seen and deleted by its owner only."""

from httpx import AsyncClient

from backend.core.encryption import encrypt_text
from backend.db.session import get_sessionmaker
from backend.modules.llm_keys.models import UserLlmKey
from backend.tests.conftest import ClientFactory

URL = "/api/v1/llm-keys/me"


async def save_old_key(client: AsyncClient) -> None:
    """A key saved before the feature was retired."""
    user_id = (await client.get("/api/v1/users/me")).json()["id"]
    async with get_sessionmaker()() as db:
        db.add(UserLlmKey(user_id=user_id, encrypted_key=encrypt_text("old-key-1234567890")))
        await db.commit()


async def test_a_new_key_is_refused_with_a_clear_reason(client: AsyncClient) -> None:
    response = await client.put(URL, json={"api_key": "good-key-1234567890"})
    assert response.status_code == 410
    assert "no longer needed" in response.json()["detail"]
    assert "good-key" not in response.text
    assert (await client.get(URL)).json()["has_key"] is False


async def test_an_old_key_can_be_deleted_by_its_owner_only(make_client: ClientFactory) -> None:
    owner, stranger = make_client(), make_client()
    await save_old_key(owner)

    assert (await stranger.get(URL)).json()["has_key"] is False
    assert (await stranger.delete(URL)).status_code == 204
    assert (await owner.get(URL)).json()["has_key"] is True

    assert (await owner.delete(URL)).status_code == 204
    assert (await owner.get(URL)).json()["has_key"] is False
