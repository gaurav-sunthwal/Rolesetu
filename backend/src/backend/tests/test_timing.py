"""Every response says how long it took and how much of that was the database."""

import re

from httpx import ASGITransport, AsyncClient

from backend.main import app


async def test_a_response_carries_its_timing() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    timing = response.headers["Server-Timing"]
    assert re.fullmatch(r'db;desc="0 queries";dur=\d+, total;dur=\d+', timing)
    assert response.headers["Timing-Allow-Origin"] == "*"
