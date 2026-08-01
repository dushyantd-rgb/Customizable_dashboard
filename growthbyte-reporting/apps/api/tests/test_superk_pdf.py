from uuid import uuid4

import pytest

from app.reports.pdf_generator import SnapshotBindingError, generate_superk_franchise_pdf


def _snapshot(snapshot_id: str) -> dict[str, object]:
    return {
        "id": snapshot_id,
        "report_month": "2026-07",
        "vertical": "b2b_franchise",
        "quality_status": "partial",
        "quality_reasons": ["Lead JSON unavailable"],
        "snapshot_version": 1,
        "formula_version": "superk-franchise-2026-08-v1",
        "metrics": [
            {
                "metric_key": "spend",
                "value": "754590.54",
                "previous_value": None,
                "percentage_change": None,
                "unit": "currency",
                "currency": "INR",
            },
            {
                "metric_key": "operational_leads",
                "value": None,
                "unit": "count",
                "currency": None,
            },
        ],
        "evidence": [],
    }


def _approved_report(snapshot_id: str) -> dict[str, object]:
    return {
        "monthly_snapshot_id": snapshot_id,
        "status": "approved",
        "content": {
            "executive_summary": [
                {
                    "statement": "Meta data is available; lead and GSC data are unavailable.",
                    "evidence_ids": ["superk_metric:" + "a" * 64],
                    "confidence": "high",
                }
            ],
            "paid_performance_summary": [],
            "lead_and_rtm_funnel": [],
            "search_console_seo_summary": [],
            "campaign_and_creative_observations": [],
            "search_query_and_page_movements": [],
            "important_wins": [],
            "important_problems": [],
            "recommended_actions": [],
            "data_reconciliation_and_limitations": [],
        },
    }


def test_pdf_uses_same_snapshot_and_renders_missing_values() -> None:
    snapshot_id = str(uuid4())

    payload = generate_superk_franchise_pdf(
        report=_approved_report(snapshot_id),
        snapshot=_snapshot(snapshot_id),
    )

    assert payload.startswith(b"%PDF")
    assert len(payload) > 2_000


def test_pdf_rejects_cross_snapshot_export() -> None:
    with pytest.raises(SnapshotBindingError, match="does not match"):
        generate_superk_franchise_pdf(
            report=_approved_report(str(uuid4())),
            snapshot=_snapshot(str(uuid4())),
        )


def test_pdf_rejects_unapproved_report() -> None:
    snapshot_id = str(uuid4())
    report = _approved_report(snapshot_id)
    report["status"] = "draft"

    with pytest.raises(SnapshotBindingError, match="approved"):
        generate_superk_franchise_pdf(report=report, snapshot=_snapshot(snapshot_id))
