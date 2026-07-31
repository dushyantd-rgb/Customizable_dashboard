from fastapi import APIRouter

from app.api.health import health
from app.models.health import HealthResponse

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def versioned_health() -> HealthResponse:
    return await health()
