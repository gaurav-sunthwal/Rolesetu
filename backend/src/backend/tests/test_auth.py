from httpx import ASGITransport, AsyncClient

from backend.main import app


async def test_protected_route_requires_a_token() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/profile/me")
    assert response.status_code == 401


async def test_garbage_token_is_rejected_not_a_server_error() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/profile/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
    assert response.status_code == 401
