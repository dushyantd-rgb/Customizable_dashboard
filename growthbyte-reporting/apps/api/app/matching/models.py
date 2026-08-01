"""Pydantic models for lead normalisation, matching, and metrics."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MatchMethod(str, Enum):
    """Deterministic matching methods."""

    EXACT_AD_ID = "exact_ad_id"
    EXACT_AD_SET_ID = "exact_ad_set_id"
    EXACT_CAMPAIGN_ID = "exact_campaign_id"
    UTM_MATCH = "utm_match"
    UNIQUE_NAME = "unique_name"
    MANUAL = "manual"
    UNMATCHED = "unmatched"


class ReviewStatus(str, Enum):
    """Review status for match decisions."""

    AUTOMATIC = "automatic"
    MANUAL_APPROVED = "manual_approved"
    MANUAL_REJECTED = "manual_rejected"


class QualityStatus(str, Enum):
    """Quality status for metric snapshots."""

    VERIFIED = "verified"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class AttributionLevel(str, Enum):
    """Attribution level for metrics."""

    CLIENT = "client"
    CAMPAIGN = "campaign"
    AD_SET = "ad_set"
    AD = "ad"


class CanonicalLeadStatus(str, Enum):
    """Canonical lead status values from the contract."""

    QUALIFIED = "qualified"
    IN_PROGRESS = "in_progress"
    INVALID = "invalid"
    DISQUALIFIED = "disqualified"
    CONVERTED = "converted"
    NOT_REVIEWED = "not_reviewed"


# Metric keys from the approved contract
METRIC_KEYS = frozenset(
    {
        "spend",
        "impressions",
        "reach",
        "clicks",
        "meta_leads",
        "imported_leads",
        "qualified_leads",
        "disqualified_leads",
        "invalid_leads",
        "converted_leads",
        "cost_per_lead",
        "cost_per_qualified_lead",
        "qualification_rate",
        "conversion_rate",
        "ctr",
        "cpc",
        "cpm",
        "unmatched_leads",
        "attribution_coverage",
    }
)


class NormalisationWarning(BaseModel):
    """Warning from lead normalisation."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    raw_field: str | None = None
    raw_value: str | None = None


class NormalisationResult(BaseModel):
    """Result of normalising a single raw row."""

    model_config = ConfigDict(extra="forbid")

    lead_record_id: UUID
    raw_row_id: UUID
    client_id: UUID
    source_lead_id: str | None = None
    lead_at: datetime | None = None
    canonical_status: str
    is_reviewed: bool
    warnings: list[NormalisationWarning] = Field(default_factory=list)
    meta_lead_id: str | None = None
    campaign_id: str | None = None
    campaign_name: str | None = None
    adset_id: str | None = None
    adset_name: str | None = None
    ad_id: str | None = None
    ad_name: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None


class NormalisationSummary(BaseModel):
    """Summary of a normalisation run."""

    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    sync_run_id: UUID
    rows_processed: int
    rows_normalised: int
    rows_rejected: int
    warnings_count: int
    finished_at: datetime


class MatchCandidate(BaseModel):
    """A candidate for lead matching."""

    model_config = ConfigDict(extra="forbid")

    entity_level: str
    external_entity_id: str
    entity_display_name: str | None = None
    campaign_id: str | None = None
    ad_set_id: str | None = None
    ad_id: str | None = None


class MatchResult(BaseModel):
    """Result of matching a single lead."""

    model_config = ConfigDict(extra="forbid")

    lead_record_id: UUID
    client_id: UUID
    method: str
    confidence: Decimal | None = None
    match_candidates: list[MatchCandidate] = Field(default_factory=list)
    matched_entity_level: str | None = None
    matched_entity_id: str | None = None
    matched_at: datetime
    rule_version: str
    review_status: str = ReviewStatus.AUTOMATIC.value


class MatchSummary(BaseModel):
    """Summary of a matching run."""

    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    leads_processed: int
    leads_matched: int
    leads_unmatched: int
    leads_ambiguous: int
    method_counts: dict[str, int]
    finished_at: datetime


class UnmatchedLead(BaseModel):
    """An unmatched lead for review."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    client_id: UUID
    source_lead_id: str | None = None
    lead_at: datetime | None = None
    campaign_name: str | None = None
    adset_name: str | None = None
    ad_name: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    source_status_raw: str | None = None
    canonical_status: str
    match_candidates: list[MatchCandidate] = Field(default_factory=list)
    candidate_count: int


class ManualMatchRequest(BaseModel):
    """Request to manually set a lead's match."""

    model_config = ConfigDict(extra="forbid")

    external_campaign_id: str | None = None
    campaign_display_name: str | None = None
    external_ad_set_id: str | None = None
    ad_set_display_name: str | None = None
    external_ad_id: str | None = None
    ad_display_name: str | None = None
    operator_label: str = Field(..., min_length=1)


class MetricValue(BaseModel):
    """A single metric value with context."""

    model_config = ConfigDict(extra="forbid")

    metric_key: str
    value: Decimal | None = None
    numerator: Decimal | None = None
    denominator: Decimal | None = None
    unit: str
    currency: str | None = None
    quality_status: str
    quality_reasons: list[str] = Field(default_factory=list)


class PeriodComparison(BaseModel):
    """Period-over-period comparison for a metric."""

    model_config = ConfigDict(extra="forbid")

    current_value: Decimal | None = None
    previous_value: Decimal | None = None
    absolute_change: Decimal | None = None
    percentage_change: Decimal | None = None
    previous_unavailable_reason: str | None = None


class KPIComparison(BaseModel):
    """Metric compared against KPI target."""

    model_config = ConfigDict(extra="forbid")

    target_value: Decimal | None = None
    variance: Decimal | None = None
    on_target: bool | None = None
    direction: str | None = None


class MetricSnapshot(BaseModel):
    """Frozen metric snapshot."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    client_id: UUID
    metric_key: str
    period_start: datetime
    period_end: datetime
    attribution_level: str
    source_entity_id: str | None = None
    entity_display_name: str | None = None
    value: Decimal | None = None
    unit: str
    currency: str | None = None
    numerator: Decimal | None = None
    denominator: Decimal | None = None
    formula_version: str
    input_cutoff_at: datetime
    calculated_at: datetime
    quality_status: str
    quality_reasons: list[str] = Field(default_factory=list)
    period_comparison: PeriodComparison | None = None
    kpi_comparison: KPIComparison | None = None


class MetricsPreviewRequest(BaseModel):
    """Request to preview metrics for a period."""

    model_config = ConfigDict(extra="forbid")

    period_start: date
    period_end: date
    attribution_level: str = Field(default=AttributionLevel.CLIENT.value)
    include_previous_period: bool = Field(default=True)
    include_kpi_comparison: bool = Field(default=True)

    @field_validator("period_end")
    @classmethod
    def period_end_after_start(cls, value: date, info: Any) -> date:
        period_start = info.data.get("period_start")
        if period_start is not None and value <= period_start:
            raise ValueError("period_end must be after period_start")
        return value


class MetricsPreviewResponse(BaseModel):
    """Response from metrics preview."""

    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    period_start: datetime
    period_end: datetime
    client_timezone: str
    currency: str
    formula_version: str
    input_cutoff_at: datetime
    metrics: list[MetricValue]
    attribution_coverage: Decimal | None = None
    unmatched_count: int
    quality_warnings: list[str] = Field(default_factory=list)


class SnapshotGenerateRequest(BaseModel):
    """Request to generate frozen metric snapshots."""

    model_config = ConfigDict(extra="forbid")

    period_start: date
    period_end: date
    attribution_levels: list[str] = Field(default_factory=lambda: [AttributionLevel.CLIENT.value])

    @field_validator("period_end")
    @classmethod
    def period_end_after_start(cls, value: date, info: Any) -> date:
        period_start = info.data.get("period_start")
        if period_start is not None and value <= period_start:
            raise ValueError("period_end must be after period_start")
        return value


class SnapshotGenerateResponse(BaseModel):
    """Response from snapshot generation."""

    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    period_start: datetime
    period_end: datetime
    snapshot_count: int
    snapshots: list[UUID]
    generated_at: datetime


class SnapshotListResponse(BaseModel):
    """Response listing snapshots."""

    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    snapshots: list[MetricSnapshot]
    total_count: int
