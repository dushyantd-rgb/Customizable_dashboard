"""API routes for lead matching and metrics."""

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.v1.dependencies import get_supabase_client
from app.data.supabase import ReportingSupabaseClientProtocol
from app.matching.matcher import LeadMatcher
from app.matching.metrics import MetricCalculator
from app.matching.models import (
    ManualMatchRequest,
    MatchSummary,
    NormalisationSummary,
    SnapshotGenerateResponse,
)

router = APIRouter(prefix="/matching", tags=["matching", "metrics"])


class NormaliseRequest(BaseModel):
    """Request to run normalisation."""

    sync_run_id: UUID | None = None


class MatchRequest(BaseModel):
    """Request to run matching."""

    pass


@router.post("/normalise", response_model=NormalisationSummary)
async def run_normalisation(
    client_id: UUID,
    request: NormaliseRequest,
    client: ReportingSupabaseClientProtocol = Depends(get_supabase_client),
) -> NormalisationSummary:
    """Normalise raw Sheet rows into canonical lead records."""
    from app.matching.normalisation import LeadNormaliser

    normaliser = LeadNormaliser(client=client)
    try:
        result = await normaliser.normalise(
            client_id=client_id,
            sync_run_id=request.sync_run_id,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "normalisation_failed", "message": str(e)},
        )


@router.post("/match", response_model=MatchSummary)
async def run_matching(
    client_id: UUID,
    request: MatchRequest,
    client: ReportingSupabaseClientProtocol = Depends(get_supabase_client),
) -> MatchSummary:
    """Run deterministic matching for unmatched leads."""
    matcher = LeadMatcher(client=client)
    try:
        result = await matcher.match_all(client_id=client_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "matching_failed", "message": str(e)},
        )


@router.get("/leads/unmatched")
async def list_unmatched(
    client_id: UUID,
    limit: int = 100,
    client: ReportingSupabaseClientProtocol = Depends(get_supabase_client),
) -> list[dict[str, Any]]:
    """List unmatched leads for manual review."""
    matcher = LeadMatcher(client=client)
    return await matcher.get_unmatched(client_id=client_id, limit=limit)


@router.get("/leads/ambiguous")
async def list_ambiguous(
    client_id: UUID,
    limit: int = 100,
    client: ReportingSupabaseClientProtocol = Depends(get_supabase_client),
) -> list[dict[str, Any]]:
    """List leads with ambiguous match candidates."""
    matcher = LeadMatcher(client=client)
    return await matcher.get_ambiguous(client_id=client_id, limit=limit)


@router.post("/leads/{lead_id}/match")
async def manual_match(
    client_id: UUID,
    lead_id: UUID,
    request: ManualMatchRequest,
    client: ReportingSupabaseClientProtocol = Depends(get_supabase_client),
) -> dict[str, Any]:
    """Submit a manual match decision for a lead."""
    matcher = LeadMatcher(client=client)
    try:
        result = await matcher.manual_match(
            client_id=client_id,
            lead_id=lead_id,
            external_campaign_id=request.external_campaign_id,
            campaign_display_name=request.campaign_display_name,
            external_ad_set_id=request.external_ad_set_id,
            ad_set_display_name=request.ad_set_display_name,
            external_ad_id=request.external_ad_id,
            ad_display_name=request.ad_display_name,
            operator_label=request.operator_label,
        )
        return {
            "lead_record_id": str(result.lead_record_id),
            "method": result.method,
            "matched_entity_level": result.matched_entity_level,
            "matched_entity_id": result.matched_entity_id,
            "review_status": result.review_status,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "manual_match_failed", "message": str(e)},
        )


# Metrics routes under separate path
metrics_router = APIRouter(prefix="/metrics", tags=["metrics"])


@metrics_router.get("")
async def preview_metrics(
    client_id: UUID,
    period_start: date,
    period_end: date,
    attribution_level: str = "client",
    client: ReportingSupabaseClientProtocol = Depends(get_supabase_client),
) -> dict[str, Any]:
    """Preview metrics for a period without generating snapshots."""
    calculator = MetricCalculator(client=client)
    try:
        result = await calculator.calculate_period_metrics(
            client_id=client_id,
            period_start=period_start,
            period_end=period_end,
            attribution_level=attribution_level,
            include_previous=True,
            include_kpi=True,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "metrics_calculation_failed", "message": str(e)},
        )


class SnapshotsGenerateBody(BaseModel):
    """Body for snapshot generation."""

    period_start: date
    period_end: date
    attribution_levels: list[str] = Field(default_factory=lambda: ["client"])


@metrics_router.post("/snapshots", response_model=SnapshotGenerateResponse)
async def generate_snapshots(
    client_id: UUID,
    body: SnapshotsGenerateBody,
    client: ReportingSupabaseClientProtocol = Depends(get_supabase_client),
) -> SnapshotGenerateResponse:
    """Generate frozen metric snapshots for a period."""
    from datetime import datetime

    calculator = MetricCalculator(client=client)
    try:
        snapshot_ids = await calculator.generate_snapshots(
            client_id=client_id,
            period_start=body.period_start,
            period_end=body.period_end,
            attribution_levels=body.attribution_levels,
        )
        return SnapshotGenerateResponse(
            client_id=client_id,
            period_start=datetime.combine(body.period_start, datetime.min.time()),
            period_end=datetime.combine(body.period_end, datetime.min.time()),
            snapshot_count=len(snapshot_ids),
            snapshots=snapshot_ids,
            generated_at=datetime.utcnow(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "snapshot_generation_failed", "message": str(e)},
        )


@metrics_router.get("/snapshots")
async def list_snapshots(
    client_id: UUID,
    period_start: date | None = None,
    period_end: date | None = None,
    limit: int = 100,
    client: ReportingSupabaseClientProtocol = Depends(get_supabase_client),
) -> list[dict[str, Any]]:
    """List metric snapshots for a client."""
    calculator = MetricCalculator(client=client)
    return await calculator.list_snapshots(
        client_id=client_id,
        period_start=period_start,
        period_end=period_end,
        limit=limit,
    )


@metrics_router.get("/snapshots/{snapshot_id}")
async def get_snapshot(
    client_id: UUID,
    snapshot_id: UUID,
    client: ReportingSupabaseClientProtocol = Depends(get_supabase_client),
) -> dict[str, Any]:
    """Get a single metric snapshot."""
    calculator = MetricCalculator(client=client)
    snapshot = await calculator.get_snapshot(
        client_id=client_id,
        snapshot_id=snapshot_id,
    )
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "snapshot_not_found", "message": "Snapshot not found"},
        )
    return snapshot
