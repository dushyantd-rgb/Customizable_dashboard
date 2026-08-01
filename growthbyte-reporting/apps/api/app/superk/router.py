"""Client-locked status and one-click generation routes for SuperK Franchise."""

from uuid import UUID

from fastapi import APIRouter

from app.superk.dependencies import SuperKServiceDependency
from app.superk.models import SuperKGenerateResponse, SuperKStatusResponse

router = APIRouter(
    prefix="/clients/{client_id}/superk-franchise-report",
    tags=["SuperK Franchise report"],
)


@router.get("/status", response_model=SuperKStatusResponse)
async def get_superk_franchise_report_status(
    client_id: UUID,
    service: SuperKServiceDependency,
) -> SuperKStatusResponse:
    return await service.get_status(client_id=client_id)


@router.post("/generate", response_model=SuperKGenerateResponse)
async def generate_superk_franchise_report(
    client_id: UUID,
    service: SuperKServiceDependency,
) -> SuperKGenerateResponse:
    """Generate the latest completed month with no request body or user choices."""

    return await service.generate(client_id=client_id)
