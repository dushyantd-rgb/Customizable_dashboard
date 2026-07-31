import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoints_do_not_expose_settings() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health_response = await client.get("/health")
        ready_response = await client.get("/ready")
        versioned_response = await client.get("/api/v1/health")

    assert health_response.status_code == 200
    assert health_response.json() == {"service": "api", "status": "ok", "version": "0.1.0"}
    assert ready_response.status_code == 200
    assert ready_response.json()["status"] == "ready"
    assert versioned_response.status_code == 200
    assert versioned_response.json() == health_response.json()
    assert "web_url" not in health_response.text
