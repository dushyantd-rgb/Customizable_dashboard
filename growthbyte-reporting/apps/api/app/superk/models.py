"""HTTP contracts for the one-click SuperK Franchise monthly report."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.superk.domain import MetricEvidence, SuperKReportOutput

SourceStatus = Literal[
    "ready",
    "succeeded",
    "partial",
    "unavailable",
    "not_configured",
    "rejected",
]


class SourceState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SourceStatus
    detail: str
    synced_at: str | None = None


class ReportWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class MonthlySnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    formula_version: str
    input_hash: str
    quality_status: Literal["verified", "partial", "unavailable"]
    metrics: tuple[MetricEvidence, ...]


class SuperKStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    vertical: Literal["b2b_franchise"]
    report_month: str
    ready_to_generate: bool
    snapshot_id: UUID | None = None
    sources: dict[str, SourceState]
    warnings: tuple[ReportWarning, ...] = ()


class SuperKGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    vertical: Literal["b2b_franchise"]
    report_month: str
    quality_status: Literal["verified", "partial", "unavailable"]
    snapshot_id: UUID
    snapshot_reused: bool
    report_id: UUID | None = None
    report_status: Literal["draft", "not_created"]
    sources: dict[str, SourceState]
    monthly_snapshot: MonthlySnapshotResponse
    sections: SuperKReportOutput
    warnings: tuple[ReportWarning, ...] = ()


def source_state(
    status: SourceStatus,
    detail: str,
    *,
    synced_at: str | None = None,
) -> SourceState:
    return SourceState(status=status, detail=detail, synced_at=synced_at)


def warning(code: str, message: str | None = None) -> ReportWarning:
    return ReportWarning(code=code, message=message or code.replace("_", " ").capitalize())


def public_knowledge(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only approved, narrative-safe knowledge fields for the GLM boundary."""

    return [
        {
            "category": row.get("category"),
            "knowledge_key": row.get("knowledge_key"),
            "value": row.get("value"),
            "version": row.get("version"),
        }
        for row in rows
    ]
