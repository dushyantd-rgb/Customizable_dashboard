import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.errors import register_error_handlers
from app.knowledge.errors import SourceDatabaseUnavailableError


@pytest.mark.asyncio
async def test_import_error_response_does_not_expose_exception_details() -> None:
    app = FastAPI()

    @app.get("/synthetic")
    async def synthetic_failure() -> None:
        raise SourceDatabaseUnavailableError("synthetic-secret-value")

    register_error_handlers(app)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/synthetic")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "knowledge_database_unavailable",
            "message": "The knowledge source is unavailable",
        }
    }
    assert "synthetic-secret-value" not in response.text
