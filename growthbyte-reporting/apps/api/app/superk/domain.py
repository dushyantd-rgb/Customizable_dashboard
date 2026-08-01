"""Pure domain contracts for the SuperK Franchise monthly report.

This module deliberately has no database, connector, logging, or HTTP dependencies.  It accepts
already-aggregated source values, calculates deterministic metrics, builds a PII-free evidence
bundle, and validates narrative output against that evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, TypeAlias
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

VERTICAL = "b2b_franchise"
FORMULA_VERSION = "superk-franchise-monthly-v1"
MAX_SOURCE_BYTES = 5 * 1024 * 1024

QualityStatus: TypeAlias = Literal["verified", "partial", "unavailable"]
DecimalInput: TypeAlias = Decimal | int | str
MetricDefinition: TypeAlias = tuple[
    str,
    Decimal | None,
    Literal["currency", "count", "percent", "position"],
    str | None,
    Decimal | None,
    Decimal | None,
]

_SOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_REPORT_MONTH_PATTERN = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])$")
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?<!\w)\+\d[\d\s().-]{7,}\d(?!\w)|\b[6-9]\d{9}\b")
_PII_LABEL_PATTERN = re.compile(
    r"\b(?:e-?mail|phone|mobile|contact number|lead name|customer name)\b",
    re.IGNORECASE,
)
_NAMED_PERSON_PATTERN = re.compile(
    r"\b(?:lead|customer|contact)\s+(?:named|name\s*(?:is|:))\b",
    re.IGNORECASE,
)
_HONORIFIC_PERSON_PATTERN = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Shri|Smt)\.?\s+[A-Z][A-Za-z'-]+",
)
_ROLE_PERSON_PATTERN = re.compile(
    r"\b(?:lead|customer|contact|owner|manager|person)\s+(?:named\s+)?"
    r"[A-Z][A-Za-z'-]+",
    re.IGNORECASE,
)
_TITLE_CASE_SEQUENCE_PATTERN = re.compile(
    r"\b(?:[A-Z][a-z]{2,})(?:\s+[A-Z][a-z]{2,}){1,2}\b",
)
_TITLE_CASE_LEADING_WORDS = frozenset(
    {"current", "monthly", "organic", "paid", "previous", "the", "verified"}
)
_ALLOWED_TITLE_CASE_PHRASES = frozenset(
    {
        "data reconciliation",
        "executive summary",
        "franchise meta",
        "google search",
        "google search console",
        "growthbyte reporting",
        "important problems",
        "important wins",
        "meta ads",
        "recommended actions",
        "reporting supabase",
        "search console",
        "super k",
        "superk franchise",
    }
)
_UNSUPPORTED_CAUSAL_PATTERN = re.compile(
    r"\b(?:because|caused by|due to|resulted in|led to|driven by|attributable to)\b",
    re.IGNORECASE,
)
_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_:-])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?")
_FIXED_TIMEZONE_FALLBACKS = {
    "UTC": UTC,
    "Etc/UTC": UTC,
    "Asia/Kolkata": timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata"),
    "Asia/Calcutta": timezone(timedelta(hours=5, minutes=30), name="Asia/Calcutta"),
}


def _contains_pii(value: str) -> bool:
    return bool(
        _EMAIL_PATTERN.search(value)
        or _PHONE_PATTERN.search(value)
        or _PII_LABEL_PATTERN.search(value)
        or _NAMED_PERSON_PATTERN.search(value)
        or _HONORIFIC_PERSON_PATTERN.search(value)
        or _ROLE_PERSON_PATTERN.search(value)
    )


def _contains_unapproved_person_name(value: str) -> bool:
    """Conservatively reject title-cased person-like names in model output."""

    for match in _TITLE_CASE_SEQUENCE_PATTERN.finditer(value):
        words = match.group(0).split()
        while words and words[0].casefold() in _TITLE_CASE_LEADING_WORDS:
            words.pop(0)
        phrase = " ".join(words).casefold()
        if phrase and phrase not in _ALLOWED_TITLE_CASE_PHRASES:
            return True
    return False


def _sanitize_comment(value: str) -> str | None:
    sanitized = " ".join(value.split())
    if not sanitized:
        return None
    if len(sanitized) > 500:
        raise ValueError("comment_too_long")
    if _contains_pii(sanitized):
        raise ValueError("comment_contains_pii")
    return sanitized


def _validate_report_month(value: str) -> str:
    if not _REPORT_MONTH_PATTERN.fullmatch(value):
        raise ValueError("invalid_report_month")
    year, month = (int(part) for part in value.split("-", maxsplit=1))
    date(year, month, 1)
    return value


class LeadAggregate(BaseModel):
    """Strict, aggregate-only operational lead input for one Franchise month."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: str
    report_month: str
    vertical: Literal["b2b_franchise"]
    total_leads: int = Field(ge=0)
    rtm_leads: int = Field(ge=0)
    comment: str | None = None

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        normalized = value.strip()
        if not _SOURCE_ID_PATTERN.fullmatch(normalized):
            raise ValueError("invalid_source_id")
        return normalized

    @field_validator("report_month")
    @classmethod
    def validate_report_month(cls, value: str) -> str:
        return _validate_report_month(value)

    @field_validator("comment", mode="before")
    @classmethod
    def sanitize_comment(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("invalid_comment")
        return _sanitize_comment(value)

    @model_validator(mode="after")
    def validate_funnel(self) -> LeadAggregate:
        if self.rtm_leads > self.total_leads:
            raise ValueError("rtm_leads_exceed_total_leads")
        return self


LeadSourceClassification: TypeAlias = Literal[
    "valid_aggregate",
    "source_vertical_mismatch",
    "invalid_json",
    "invalid_aggregate",
    "row_level_requires_confirmation",
    "payload_too_large",
    "source_unavailable",
]


class LeadSourceInspection(BaseModel):
    """Payload-safe source inspection result; it never contains raw source data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    classification: LeadSourceClassification
    payload_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    aggregate: LeadAggregate | None = None


def latest_completed_report_month(
    timezone_name: str,
    *,
    now: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
) -> str:
    """Return the latest fully completed calendar month in ``timezone_name``."""

    if now is not None and clock is not None:
        raise ValueError("supply_now_or_clock_not_both")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        timezone = _FIXED_TIMEZONE_FALLBACKS.get(timezone_name)
        if timezone is None:
            raise ValueError("invalid_timezone") from error
    instant = now if now is not None else (clock() if clock is not None else datetime.now(UTC))
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("current_time_must_be_timezone_aware")
    local_instant = instant.astimezone(timezone)
    previous_month_day = local_instant.date().replace(day=1) - timedelta(days=1)
    return previous_month_day.strftime("%Y-%m")


def _decode_json(payload: bytes | bytearray | str) -> Any:
    text = bytes(payload).decode("utf-8") if isinstance(payload, bytes | bytearray) else payload
    return json.loads(text, parse_float=Decimal)


def _normalized_decimal_string(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("non_finite_number")
    normalized = value.normalize()
    return format(normalized, "f") if normalized != 0 else "0"


def _canonicalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="python"))
    if isinstance(value, Decimal):
        return {"$decimal": _normalized_decimal_string(value)}
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_canonicalize(item) for item in value]
    if value is None or isinstance(value, str | int | bool):
        return value
    if isinstance(value, float):
        return {"$decimal": _normalized_decimal_string(Decimal(str(value)))}
    raise TypeError("unsupported_canonical_json_value")


def canonical_json_sha256(
    value: bytes | bytearray | str | BaseModel | Mapping[str, Any] | Sequence[Any],
) -> str:
    """Hash canonical JSON; object key order and insignificant whitespace do not affect it."""

    parsed = _decode_json(value) if isinstance(value, bytes | bytearray | str) else value
    canonical = json.dumps(
        _canonicalize(parsed),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _looks_like_purchase_export(parsed: Any) -> bool:
    if not isinstance(parsed, list) or not parsed or not isinstance(parsed[0], Mapping):
        return False
    keys = {str(key).strip().casefold() for key in parsed[0]}
    has_purchase_metric = any(key == "purchases" or key.startswith("purchase roas") for key in keys)
    has_meta_grain = {"day", "campaign name", "ad set name", "ad name"}.issubset(keys)
    return has_purchase_metric and has_meta_grain


def inspect_lead_source(
    source: bytes | bytearray | Path | str,
    *,
    filename: str | None = None,
) -> LeadSourceInspection:
    """Classify lead input without logging or returning the payload or validation contents."""

    if isinstance(source, Path | str):
        path = Path(source)
        filename = filename or path.name
        try:
            payload = path.read_bytes()
        except OSError:
            return LeadSourceInspection(classification="source_unavailable")
    else:
        payload = bytes(source)

    if len(payload) > MAX_SOURCE_BYTES:
        return LeadSourceInspection(
            classification="payload_too_large",
            payload_hash=hashlib.sha256(payload).hexdigest(),
        )

    try:
        parsed = _decode_json(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return LeadSourceInspection(
            classification="invalid_json",
            payload_hash=hashlib.sha256(payload).hexdigest(),
        )

    payload_hash = canonical_json_sha256(parsed)
    normalized_filename = (filename or "").casefold()
    if "qcom" in normalized_filename or _looks_like_purchase_export(parsed):
        return LeadSourceInspection(
            classification="source_vertical_mismatch",
            payload_hash=payload_hash,
        )

    if isinstance(parsed, Mapping):
        supplied_vertical = parsed.get("vertical")
        if supplied_vertical is not None and supplied_vertical != VERTICAL:
            return LeadSourceInspection(
                classification="source_vertical_mismatch",
                payload_hash=payload_hash,
            )
        try:
            aggregate = LeadAggregate.model_validate(parsed)
        except ValidationError:
            return LeadSourceInspection(
                classification="invalid_aggregate",
                payload_hash=payload_hash,
            )
        return LeadSourceInspection(
            classification="valid_aggregate",
            payload_hash=payload_hash,
            aggregate=aggregate,
        )

    if isinstance(parsed, list):
        return LeadSourceInspection(
            classification="row_level_requires_confirmation",
            payload_hash=payload_hash,
        )
    return LeadSourceInspection(
        classification="invalid_aggregate",
        payload_hash=payload_hash,
    )


def _to_decimal(value: DecimalInput | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("boolean_is_not_numeric")
    try:
        converted = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("invalid_decimal") from error
    if not converted.is_finite():
        raise ValueError("non_finite_number")
    return converted


def safe_divide(
    numerator: DecimalInput | None,
    denominator: DecimalInput | None,
) -> Decimal | None:
    """Return an exact Decimal quotient, or ``None`` for missing/zero denominators."""

    left = _to_decimal(numerator)
    right = _to_decimal(denominator)
    if left is None or right is None or right == 0:
        return None
    return left / right


class PaidAggregate(BaseModel):
    """Period-level paid inputs; reach must be Meta's period-level response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    vertical: Literal["b2b_franchise"] = VERTICAL
    spend: Decimal | None = Field(default=None, ge=0)
    link_clicks: int | None = Field(default=None, ge=0)
    impressions: int | None = Field(default=None, ge=0)
    period_reach: int | None = Field(default=None, ge=0)
    meta_reported_leads: int | None = Field(default=None, ge=0)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")


class GscTotals(BaseModel):
    """GSC's separately queried period totals; CTR and position are passed through."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    vertical: Literal["b2b_franchise"] = VERTICAL
    clicks: Decimal | None = Field(default=None, ge=0)
    impressions: Decimal | None = Field(default=None, ge=0)
    ctr_percent: Decimal | None = Field(default=None, ge=0, le=100)
    average_position: Decimal | None = Field(default=None, ge=0)


class MetricEvidence(BaseModel):
    """One deterministic metric and its comparison/KPI lineage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str = Field(pattern=r"^superk_metric:[a-f0-9]{64}$")
    metric_key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    value: Decimal | None
    unit: Literal["currency", "count", "percent", "position"]
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    numerator: Decimal | None = None
    denominator: Decimal | None = None
    previous_value: Decimal | None = None
    absolute_change: Decimal | None = None
    percentage_change: Decimal | None = None
    kpi_target: Decimal | None = None
    kpi_variance: Decimal | None = None
    quality_status: QualityStatus
    formula_version: str


class MonthlyMetricResult(BaseModel):
    """Deterministic monthly calculation output before narrative generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    client_id: UUID
    vertical: Literal["b2b_franchise"]
    report_month: str
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    formula_version: str
    quality_status: QualityStatus
    warnings: tuple[str, ...]
    metrics: tuple[MetricEvidence, ...]

    def metric(self, metric_key: str) -> MetricEvidence:
        for metric in self.metrics:
            if metric.metric_key == metric_key:
                return metric
        raise KeyError(metric_key)


class EvidenceBundle(BaseModel):
    """Allowlisted aggregate evidence. It has no comment, PII, or raw-row fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    client_id: UUID
    vertical: Literal["b2b_franchise"]
    report_month: str
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    formula_version: str
    quality_status: QualityStatus
    quality_warnings: tuple[str, ...]
    evidence: tuple[MetricEvidence, ...]
    evidence_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_evidence_index(self) -> EvidenceBundle:
        actual_ids = tuple(item.evidence_id for item in self.evidence)
        if self.evidence_ids != actual_ids or len(actual_ids) != len(set(actual_ids)):
            raise ValueError("invalid_evidence_index")
        return self

    @property
    def warnings(self) -> tuple[str, ...]:
        """Compatibility accessor for metric-result callers."""

        return self.quality_warnings

    @property
    def evidence_by_id(self) -> dict[str, MetricEvidence]:
        return {item.evidence_id: item for item in self.evidence}


def _stable_evidence_id(
    *,
    client_id: UUID,
    report_month: str,
    input_hash: str,
    metric_key: str,
    formula_version: str,
) -> str:
    digest = canonical_json_sha256(
        {
            "client_id": client_id,
            "vertical": VERTICAL,
            "report_month": report_month,
            "input_hash": input_hash,
            "metric_key": metric_key,
            "formula_version": formula_version,
        }
    )
    return f"superk_metric:{digest}"


def _decimal_mapping(values: Mapping[str, DecimalInput | None] | None) -> dict[str, Decimal | None]:
    if values is None:
        return {}
    return {key: _to_decimal(value) for key, value in values.items()}


def calculate_monthly_metrics(
    *,
    client_id: UUID,
    report_month: str,
    paid: PaidAggregate | None,
    leads: LeadAggregate | None,
    gsc: GscTotals | None = None,
    previous_values: Mapping[str, DecimalInput | None] | None = None,
    kpi_targets: Mapping[str, DecimalInput | None] | None = None,
    reconciliation_threshold_percent: DecimalInput = Decimal("10"),
    formula_version: str = FORMULA_VERSION,
) -> MonthlyMetricResult:
    """Calculate paid, funnel, reconciliation, and GSC metrics from aggregate inputs."""

    report_month = _validate_report_month(report_month)
    if leads is not None and leads.report_month != report_month:
        raise ValueError("lead_report_month_mismatch")
    threshold = _to_decimal(reconciliation_threshold_percent)
    if threshold is None or threshold < 0:
        raise ValueError("invalid_reconciliation_threshold")
    previous = _decimal_mapping(previous_values)
    kpis = _decimal_mapping(kpi_targets)

    input_hash = canonical_json_sha256(
        {
            "client_id": client_id,
            "vertical": VERTICAL,
            "report_month": report_month,
            "formula_version": formula_version,
            "paid": paid,
            "leads": leads,
            "gsc": gsc,
            "previous_values": previous,
            "kpi_targets": kpis,
            "reconciliation_threshold_percent": threshold,
        }
    )

    spend = paid.spend if paid is not None else None
    clicks = Decimal(paid.link_clicks) if paid and paid.link_clicks is not None else None
    impressions = Decimal(paid.impressions) if paid and paid.impressions is not None else None
    reach = Decimal(paid.period_reach) if paid and paid.period_reach is not None else None
    meta_leads = (
        Decimal(paid.meta_reported_leads) if paid and paid.meta_reported_leads is not None else None
    )
    operational_leads = Decimal(leads.total_leads) if leads is not None else None
    rtm_leads = Decimal(leads.rtm_leads) if leads is not None else None

    cpc = safe_divide(spend, clicks)
    cpm_base = safe_divide(spend, impressions)
    cpm = cpm_base * Decimal("1000") if cpm_base is not None else None
    ctr_base = safe_divide(clicks, impressions)
    ctr = ctr_base * Decimal("100") if ctr_base is not None else None
    cpl = safe_divide(spend, operational_leads)
    rtm_rate_base = safe_divide(rtm_leads, operational_leads)
    rtm_rate = rtm_rate_base * Decimal("100") if rtm_rate_base is not None else None
    cost_per_rtm = safe_divide(spend, rtm_leads)
    click_to_lead_base = safe_divide(operational_leads, clicks)
    click_to_lead = click_to_lead_base * Decimal("100") if click_to_lead_base is not None else None
    lead_difference = (
        meta_leads - operational_leads
        if meta_leads is not None and operational_leads is not None
        else None
    )
    absolute_lead_difference = abs(lead_difference) if lead_difference is not None else None
    difference_base = safe_divide(absolute_lead_difference, operational_leads)
    difference_percent = difference_base * Decimal("100") if difference_base is not None else None

    warnings: list[str] = []
    if paid is None:
        warnings.append("paid_data_missing")
    elif paid.period_reach is None:
        warnings.append("period_reach_unavailable")
    if leads is None:
        warnings.append("operational_leads_missing")
    if gsc is None:
        warnings.append("gsc_data_missing")
    if lead_difference not in (None, Decimal("0")):
        material = operational_leads == 0 or (
            difference_percent is not None and difference_percent >= threshold
        )
        if material:
            warnings.append("meta_operational_lead_reconciliation_required")

    paid_complete = paid is not None and all(
        value is not None
        for value in (paid.spend, paid.link_clicks, paid.impressions, paid.period_reach)
    )
    gsc_complete = gsc is not None and all(
        value is not None
        for value in (gsc.clicks, gsc.impressions, gsc.ctr_percent, gsc.average_position)
    )
    if paid is None and leads is None and gsc is None:
        overall_quality: QualityStatus = "unavailable"
    elif paid_complete and leads is not None and gsc_complete:
        overall_quality = "verified"
    else:
        overall_quality = "partial"

    currency = paid.currency if paid is not None else "INR"
    definitions: tuple[MetricDefinition, ...] = (
        ("spend", spend, "currency", currency, None, None),
        ("link_clicks", clicks, "count", None, None, None),
        ("impressions", impressions, "count", None, None, None),
        ("period_reach", reach, "count", None, None, None),
        ("meta_reported_leads", meta_leads, "count", None, None, None),
        ("operational_leads", operational_leads, "count", None, None, None),
        ("rtm_leads", rtm_leads, "count", None, None, None),
        ("cpc", cpc, "currency", currency, spend, clicks),
        ("cpm", cpm, "currency", currency, spend, impressions),
        ("ctr", ctr, "percent", None, clicks, impressions),
        ("cost_per_lead", cpl, "currency", currency, spend, operational_leads),
        (
            "rtm_conversion_rate",
            rtm_rate,
            "percent",
            None,
            rtm_leads,
            operational_leads,
        ),
        ("cost_per_rtm", cost_per_rtm, "currency", currency, spend, rtm_leads),
        (
            "click_to_lead_conversion_rate",
            click_to_lead,
            "percent",
            None,
            operational_leads,
            clicks,
        ),
        (
            "meta_operational_lead_difference",
            lead_difference,
            "count",
            None,
            meta_leads,
            operational_leads,
        ),
        (
            "meta_operational_lead_difference_percent",
            difference_percent,
            "percent",
            None,
            absolute_lead_difference,
            operational_leads,
        ),
        ("organic_clicks", gsc.clicks if gsc else None, "count", None, None, None),
        (
            "organic_impressions",
            gsc.impressions if gsc else None,
            "count",
            None,
            None,
            None,
        ),
        ("organic_ctr", gsc.ctr_percent if gsc else None, "percent", None, None, None),
        (
            "organic_average_position",
            gsc.average_position if gsc else None,
            "position",
            None,
            None,
            None,
        ),
    )

    metrics: list[MetricEvidence] = []
    for metric_key, value, unit, metric_currency, numerator, denominator in definitions:
        previous_value = previous.get(metric_key)
        absolute_change = (
            value - previous_value if value is not None and previous_value is not None else None
        )
        previous_change_base = safe_divide(
            absolute_change,
            abs(previous_value) if previous_value is not None else None,
        )
        percentage_change = (
            previous_change_base * Decimal("100") if previous_change_base is not None else None
        )
        kpi_target = kpis.get(metric_key)
        kpi_variance = value - kpi_target if value is not None and kpi_target is not None else None
        metrics.append(
            MetricEvidence(
                evidence_id=_stable_evidence_id(
                    client_id=client_id,
                    report_month=report_month,
                    input_hash=input_hash,
                    metric_key=metric_key,
                    formula_version=formula_version,
                ),
                metric_key=metric_key,
                value=value,
                unit=unit,
                currency=metric_currency,
                numerator=numerator,
                denominator=denominator,
                previous_value=previous_value,
                absolute_change=absolute_change,
                percentage_change=percentage_change,
                kpi_target=kpi_target,
                kpi_variance=kpi_variance,
                quality_status="verified" if value is not None else "unavailable",
                formula_version=formula_version,
            )
        )

    return MonthlyMetricResult(
        client_id=client_id,
        vertical=VERTICAL,
        report_month=report_month,
        input_hash=input_hash,
        formula_version=formula_version,
        quality_status=overall_quality,
        warnings=tuple(warnings),
        metrics=tuple(metrics),
    )


def build_evidence_bundle(result: MonthlyMetricResult) -> EvidenceBundle:
    """Build the only aggregate payload intended for an MCP/GLM boundary."""

    return EvidenceBundle(
        client_id=result.client_id,
        vertical=result.vertical,
        report_month=result.report_month,
        input_hash=result.input_hash,
        formula_version=result.formula_version,
        quality_status=result.quality_status,
        quality_warnings=result.warnings,
        evidence=result.metrics,
        evidence_ids=tuple(item.evidence_id for item in result.metrics),
    )


class ReportClaim(BaseModel):
    """One report statement with explicit evidence and epistemic classification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(min_length=1)
    confidence: Literal["high", "medium", "low"]
    limitation: str | None = Field(default=None, max_length=1000)

    @field_validator("statement")
    @classmethod
    def normalize_statement(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("empty_statement")
        return normalized

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate_evidence_id")
        return value

    @field_validator("limitation")
    @classmethod
    def normalize_limitation(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class SuperKReportOutput(BaseModel):
    """The exact ten-section SuperK Franchise narrative contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    executive_summary: list[ReportClaim] = Field(min_length=1)
    paid_performance_summary: list[ReportClaim] = Field(min_length=1)
    lead_and_rtm_funnel: list[ReportClaim] = Field(min_length=1)
    search_console_seo_summary: list[ReportClaim] = Field(min_length=1)
    campaign_and_creative_observations: list[ReportClaim] = Field(min_length=1)
    search_query_and_page_movements: list[ReportClaim] = Field(min_length=1)
    important_wins: list[ReportClaim] = Field(min_length=1)
    important_problems: list[ReportClaim] = Field(min_length=1)
    recommended_actions: list[ReportClaim] = Field(min_length=1)
    data_reconciliation_and_limitations: list[ReportClaim] = Field(min_length=1)

    def iter_claims(self) -> tuple[ReportClaim, ...]:
        return tuple(
            claim
            for section in (
                self.executive_summary,
                self.paid_performance_summary,
                self.lead_and_rtm_funnel,
                self.search_console_seo_summary,
                self.campaign_and_creative_observations,
                self.search_query_and_page_movements,
                self.important_wins,
                self.important_problems,
                self.recommended_actions,
                self.data_reconciliation_and_limitations,
            )
            for claim in section
        )


class ReportValidationError(ValueError):
    """Safe report-validation error identified only by an allowlisted code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _numeric_candidates(evidence: MetricEvidence) -> tuple[Decimal, ...]:
    values = (
        evidence.value,
        evidence.numerator,
        evidence.denominator,
        evidence.previous_value,
        evidence.absolute_change,
        evidence.percentage_change,
        evidence.kpi_target,
        evidence.kpi_variance,
    )
    return tuple(value for value in values if value is not None)


def _matches_evidence_number(claimed: Decimal, candidates: Sequence[Decimal]) -> bool:
    for candidate in candidates:
        if claimed == candidate:
            return True
        for places in range(0, 7):
            quantum = Decimal("1").scaleb(-places)
            if claimed == candidate.quantize(quantum, rounding=ROUND_HALF_UP):
                return True
    return False


def _extract_claimed_numbers(statement: str) -> tuple[Decimal, ...]:
    extracted: list[Decimal] = []
    for match in _NUMBER_PATTERN.finditer(statement):
        token = match.group(0)
        has_percent = token.endswith("%")
        normalized = token.removesuffix("%").replace(",", "")
        try:
            value = Decimal(normalized)
        except InvalidOperation:
            continue
        if (
            not has_percent
            and value == value.to_integral()
            and Decimal("1900") <= value <= Decimal("2100")
        ):
            continue
        extracted.append(value)
    return tuple(extracted)


def validate_report_output(
    output: SuperKReportOutput | Mapping[str, Any] | bytes | str,
    *,
    evidence_bundle: EvidenceBundle,
) -> SuperKReportOutput:
    """Reject malformed, unsupported, causal, PII-bearing, or invented report claims."""

    try:
        if isinstance(output, SuperKReportOutput):
            report = output
        elif isinstance(output, bytes | str):
            report = SuperKReportOutput.model_validate_json(output)
        else:
            report = SuperKReportOutput.model_validate(output)
    except (ValidationError, ValueError, TypeError) as error:
        raise ReportValidationError("invalid_report_output") from error

    known_evidence = evidence_bundle.evidence_by_id
    for claim in report.iter_claims():
        claim_texts = (claim.statement,) + ((claim.limitation,) if claim.limitation else ())
        if any(
            _contains_pii(text) or _contains_unapproved_person_name(text) for text in claim_texts
        ):
            raise ReportValidationError("pii_detected")
        unknown_ids = set(claim.evidence_ids).difference(known_evidence)
        if unknown_ids:
            raise ReportValidationError("unknown_evidence_id")
        if _UNSUPPORTED_CAUSAL_PATTERN.search(claim.statement):
            raise ReportValidationError("unsupported_causal_claim")
        candidates = tuple(
            number
            for evidence_id in claim.evidence_ids
            for number in _numeric_candidates(known_evidence[evidence_id])
        )
        for text in claim_texts:
            for claimed_number in _extract_claimed_numbers(text):
                if not _matches_evidence_number(claimed_number, candidates):
                    raise ReportValidationError("unsupported_numeric_claim")
    return report
