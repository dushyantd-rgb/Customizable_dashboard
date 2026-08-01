from fastapi import APIRouter, Request

from app.api.health import health
from app.api.v1.clients import router as clients_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.kpis import router as kpis_router
from app.integrations.google.router import router as google_router
from app.integrations.meta.router import router as meta_router
from app.matching.router import metrics_router
from app.matching.router import router as matching_router
from app.models.health import HealthResponse
from app.superk.router import router as superk_router

router = APIRouter(prefix="/api/v1")
router.include_router(clients_router)
router.include_router(knowledge_router)
router.include_router(kpis_router)
router.include_router(meta_router)
router.include_router(google_router)
router.include_router(matching_router)
router.include_router(metrics_router)
router.include_router(superk_router)


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def versioned_health(request: Request) -> HealthResponse:
    return await health(request)
