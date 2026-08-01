"""Unit tests for the isolated SuperK Franchise reporting domain."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.superk.domain import (
    VERTICAL,
    GscTotals,
    LeadAggregate,
    PaidAggregate,
    ReportValidationError,
    build_evidence_bundle,
    calculate_monthly_metrics,
    canonical_json_sha256,
    inspect_lead_source,
    latest_completed_report_month,
    safe_divide,
    validate_report_output,
)

CLIENT_ID = UUID("11111111-1111-1111-1111-111111111111")

REPORT_SECTION_KEYS = (
    "executive_summary",
    "paid_performance_summary",
    "lead_and_rtm_funnel",
    "search_console_seo_summary",
    "campaign_and_creative_observations",
    "search_query_and_page_movements",
    "important_wins",
    "important_problems",
    "recommended_actions",
    "data_reconciliation_and_limitations",
)


def _lead(**overrides: object) -> LeadAggregate:
    values: dict[str, object] = {
        "source_id": "superk-franchise-2026-07",
        "report_month": "2026-07",
        "vertical": VERTICAL,
        "total_leads": 100,
        "rtm_leads": 25,
        "comment": "Operational aggregate confirmed",
    }
    values.update(overrides)
    return LeadAggregate.model_validate(values)


def _paid(**overrides: object) -> PaidAggregate:
    values: dict[str, object] = {
        "spend": Decimal("1000"),
        "link_clicks": 100,
        "impressions": 10_000,
        "period_reach": 5_000,
        "meta_reported_leads": 120,
        "currency": "INR",
    }
    values.update(overrides)
    return PaidAggregate.model_validate(values)


def _gsc() -> GscTotals:
    return GscTotals(
        clicks=Decimal("250"),
        impressions=Decimal("5000"),
        ctr_percent=Decimal("3.25"),
        average_position=Decimal("8.75"),
    )


def _result():
    return calculate_monthly_metrics(
        client_id=CLIENT_ID,
        report_month="2026-07",
        paid=_paid(),
        leads=_lead(),
        gsc=_gsc(),
        previous_values={"cost_per_lead": Decimal("8")},
        kpi_targets={"cost_per_lead": Decimal("9")},
    )


def _report_payload(evidence_id: str, statement: str = "The verified metric is available."):
    claim = {
        "statement": statement,
        "evidence_ids": [evidence_id],
        "confidence": "high",
        "limitation": None,
    }
    return {key: [claim.copy()] for key in REPORT_SECTION_KEYS}


def test_latest_completed_month_uses_supplied_timezone() -> None:
    instant = datetime(2026, 7, 31, 20, 0, tzinfo=UTC)

    assert latest_completed_report_month("Asia/Kolkata", now=instant) == "2026-07"
    assert latest_completed_report_month("UTC", now=instant) == "2026-06"


def test_latest_completed_month_accepts_injected_clock() -> None:
    assert (
        latest_completed_report_month(
            "UTC",
            clock=lambda: datetime(2026, 1, 15, tzinfo=UTC),
        )
        == "2025-12"
    )


def test_lead_aggregate_is_strict_and_sanitizes_comment() -> None:
    lead = _lead(comment="  Confirmed\nwithout\tPII  ")

    assert lead.comment == "Confirmed without PII"
    assert lead.vertical == "b2b_franchise"


@pytest.mark.parametrize(
    "updates",
    [
        {"vertical": "qcom"},
        {"report_month": "2026-13"},
        {"total_leads": -1},
        {"rtm_leads": -1},
        {"total_leads": 10, "rtm_leads": 11},
        {"total_leads": "100"},
        {"unexpected": "field"},
        {"comment": "Contact jane@example.com for details"},
        {"comment": "Call mobile 9876543210"},
    ],
)
def test_lead_aggregate_rejects_invalid_or_sensitive_input(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _lead(**updates)


def test_invalid_json_is_classified_without_returning_payload() -> None:
    inspection = inspect_lead_source(b'{"source_id":')

    assert inspection.classification == "invalid_json"
    assert inspection.payload_hash is not None
    assert inspection.aggregate is None
    assert "source_id" not in inspection.model_dump_json()


def test_qcom_purchase_export_is_explicit_vertical_mismatch(tmp_path) -> None:
    purchase_rows = [
        {
            "Day": "2026-07-01",
            "Campaign name": "redacted",
            "Ad set name": "redacted",
            "Ad name": "redacted",
            "Purchases": "10",
        }
    ]
    payload = json.dumps(purchase_rows).encode()
    path = tmp_path / "superk_purchase_qcom.json"
    path.write_bytes(payload)

    assert inspect_lead_source(payload).classification == "source_vertical_mismatch"
    assert inspect_lead_source(path).classification == "source_vertical_mismatch"
    assert inspect_lead_source(b'{"vertical":"qcom"}').classification == "source_vertical_mismatch"


def test_valid_aggregate_and_row_level_sources_are_distinguished() -> None:
    valid = json.dumps(_lead().model_dump(mode="json")).encode()

    inspected = inspect_lead_source(valid, filename="franchise-leads.json")
    row_level = inspect_lead_source(b'[{"lead_id":"anonymous"}]')

    assert inspected.classification == "valid_aggregate"
    assert inspected.aggregate == _lead()
    assert row_level.classification == "row_level_requires_confirmation"


def test_canonical_payload_hash_is_independent_of_key_order_and_whitespace() -> None:
    first = b'{"b":2,"a":{"d":4,"c":3}}'
    second = b' { "a" : { "c" : 3, "d" : 4 }, "b" : 2 } '

    assert canonical_json_sha256(first) == canonical_json_sha256(second)


def test_safe_divide_preserves_zero_and_rejects_missing_or_zero_denominator() -> None:
    assert safe_divide(Decimal("0"), Decimal("5")) == Decimal("0")
    assert safe_divide(Decimal("1"), Decimal("4")) == Decimal("0.25")
    assert safe_divide(Decimal("1"), Decimal("0")) is None
    assert safe_divide(None, Decimal("1")) is None
    assert safe_divide(Decimal("1"), None) is None


def test_deterministic_paid_funnel_gsc_comparison_and_kpi_metrics() -> None:
    result = _result()

    assert result.quality_status == "verified"
    assert result.metric("cpc").value == Decimal("10")
    assert result.metric("cpm").value == Decimal("100")
    assert result.metric("ctr").value == Decimal("1")
    assert result.metric("cost_per_lead").value == Decimal("10")
    assert result.metric("rtm_conversion_rate").value == Decimal("25")
    assert result.metric("cost_per_rtm").value == Decimal("40")
    assert result.metric("click_to_lead_conversion_rate").value == Decimal("100")
    assert result.metric("period_reach").value == Decimal("5000")
    assert result.metric("organic_ctr").value == Decimal("3.25")
    assert result.metric("organic_average_position").value == Decimal("8.75")

    cpl = result.metric("cost_per_lead")
    assert cpl.previous_value == Decimal("8")
    assert cpl.absolute_change == Decimal("2")
    assert cpl.percentage_change == Decimal("25")
    assert cpl.kpi_target == Decimal("9")
    assert cpl.kpi_variance == Decimal("1")


def test_metrics_and_evidence_ids_are_stable_for_identical_inputs() -> None:
    first = _result()
    second = _result()

    assert first.input_hash == second.input_hash
    assert [item.evidence_id for item in first.metrics] == [
        item.evidence_id for item in second.metrics
    ]


def test_zero_denominators_are_unavailable_not_zero_or_infinity() -> None:
    result = calculate_monthly_metrics(
        client_id=CLIENT_ID,
        report_month="2026-07",
        paid=_paid(link_clicks=0, impressions=0, meta_reported_leads=0),
        leads=_lead(total_leads=0, rtm_leads=0),
    )

    for metric_key in (
        "cpc",
        "cpm",
        "ctr",
        "cost_per_lead",
        "rtm_conversion_rate",
        "cost_per_rtm",
        "click_to_lead_conversion_rate",
    ):
        metric = result.metric(metric_key)
        assert metric.value is None
        assert metric.quality_status == "unavailable"
    assert result.metric("link_clicks").value == Decimal("0")
    assert result.metric("operational_leads").value == Decimal("0")


def test_meta_operational_reconciliation_is_explicit_and_material() -> None:
    result = _result()

    assert result.metric("meta_operational_lead_difference").value == Decimal("20")
    assert result.metric("meta_operational_lead_difference_percent").value == Decimal("20")
    assert "meta_operational_lead_reconciliation_required" in result.warnings


def test_nonmaterial_reconciliation_difference_does_not_warn() -> None:
    result = calculate_monthly_metrics(
        client_id=CLIENT_ID,
        report_month="2026-07",
        paid=_paid(meta_reported_leads=105),
        leads=_lead(),
        gsc=_gsc(),
    )

    assert "meta_operational_lead_reconciliation_required" not in result.warnings


def test_evidence_bundle_exposes_only_allowlisted_aggregates() -> None:
    bundle = build_evidence_bundle(_result())
    serialized = bundle.model_dump_json().casefold()

    assert "operational aggregate confirmed" not in serialized
    assert "comment" not in serialized
    assert "raw_rows" not in serialized
    assert "email" not in serialized
    assert "phone" not in serialized
    assert len(bundle.evidence_by_id) == len(bundle.evidence)
    assert bundle.evidence_ids == tuple(item.evidence_id for item in bundle.evidence)
    assert bundle.quality_warnings == bundle.warnings


def test_report_validates_all_ten_sections_and_executive_numeric_claim() -> None:
    bundle = build_evidence_bundle(_result())
    spend_id = _result().metric("spend").evidence_id
    payload = _report_payload(spend_id, "Verified spend was 1000.")

    report = validate_report_output(payload, evidence_bundle=bundle)

    assert set(report.model_dump()) == set(REPORT_SECTION_KEYS)
    assert report.executive_summary[0].statement == "Verified spend was 1000."


def test_report_rejects_unknown_evidence_id() -> None:
    bundle = build_evidence_bundle(_result())
    payload = _report_payload("superk_metric:" + "0" * 64)

    with pytest.raises(ReportValidationError, match="unknown_evidence_id"):
        validate_report_output(payload, evidence_bundle=bundle)


def test_report_rejects_invented_number_in_executive_summary() -> None:
    result = _result()
    bundle = build_evidence_bundle(result)
    payload = _report_payload(result.metric("spend").evidence_id)
    payload["executive_summary"][0]["statement"] = "Verified spend was 999999."

    with pytest.raises(ReportValidationError, match="unsupported_numeric_claim"):
        validate_report_output(payload, evidence_bundle=bundle)


@pytest.mark.parametrize(
    "statement",
    [
        "Contact jane@example.com about this lead.",
        "Call mobile 9876543210 for more detail.",
        "The customer named Jane reported the issue.",
    ],
)
def test_report_rejects_pii(statement: str) -> None:
    result = _result()
    bundle = build_evidence_bundle(result)
    payload = _report_payload(result.metric("spend").evidence_id)
    payload["important_problems"][0]["statement"] = statement

    with pytest.raises(ReportValidationError, match="pii_detected"):
        validate_report_output(payload, evidence_bundle=bundle)


@pytest.mark.parametrize(
    "statement",
    (
        "Jane Smith reported the issue.",
        "Mr Rahul reported the issue.",
        "The customer Rahul reported the issue.",
    ),
)
def test_report_rejects_person_names(statement: str) -> None:
    result = _result()
    bundle = build_evidence_bundle(result)
    payload = _report_payload(bundle.evidence_ids[0])
    payload["important_problems"][0]["statement"] = statement

    with pytest.raises(ReportValidationError, match="pii_detected"):
        validate_report_output(payload, evidence_bundle=bundle)


def test_report_rejects_unsupported_causal_attribution() -> None:
    result = _result()
    bundle = build_evidence_bundle(result)
    payload = _report_payload(result.metric("operational_leads").evidence_id)
    payload["important_problems"][0]["statement"] = "Leads declined because the creative was weak."

    with pytest.raises(ReportValidationError, match="unsupported_causal_claim"):
        validate_report_output(payload, evidence_bundle=bundle)


def test_report_rejects_missing_section_and_extra_claim_fields() -> None:
    result = _result()
    bundle = build_evidence_bundle(result)
    missing = _report_payload(result.metric("spend").evidence_id)
    missing.pop("recommended_actions")

    with pytest.raises(ReportValidationError, match="invalid_report_output"):
        validate_report_output(missing, evidence_bundle=bundle)

    extra = _report_payload(result.metric("spend").evidence_id)
    extra["executive_summary"][0]["raw_rows"] = []
    with pytest.raises(ReportValidationError, match="invalid_report_output"):
        validate_report_output(extra, evidence_bundle=bundle)
