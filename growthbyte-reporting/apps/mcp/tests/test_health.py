import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, mcp_transport


@pytest.mark.asyncio
async def test_health_and_transport_foundation() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health_response = await client.get("/health")
        ready_response = await client.get("/ready")

    assert health_response.status_code == 200
    assert health_response.json() == {"service": "mcp", "status": "ok", "version": "0.1.0"}
    assert ready_response.status_code == 200
    assert ready_response.json()["status"] == "ready"
    assert any(route.path == "/mcp" for route in mcp_transport.routes)
