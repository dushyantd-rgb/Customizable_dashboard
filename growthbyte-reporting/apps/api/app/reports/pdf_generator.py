"""SuperK Franchise PDF rendering based on one immutable monthly snapshot.

This adapts the Phase 6 ReportLab prototype while keeping the dashboard/PDF
binding explicit and displaying absent values as ``Unavailable``.
"""

from __future__ import annotations

import io
from html import escape
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

TEAL = colors.HexColor("#009389")
AMBER = colors.HexColor("#935600")
INK = colors.HexColor("#0B0B0B")
MUTED = colors.HexColor("#626262")
PAPER = colors.white


class SnapshotBindingError(ValueError):
    """Raised when a report and PDF input do not reference the same snapshot."""


def generate_superk_franchise_pdf(
    *,
    report: dict[str, Any],
    snapshot: dict[str, Any],
) -> bytes:
    """Render an approved report from the exact dashboard snapshot."""

    report_snapshot_id = str(report.get("monthly_snapshot_id") or report.get("snapshot_id") or "")
    snapshot_id = str(snapshot.get("id") or snapshot.get("snapshot_id") or "")
    if not report_snapshot_id or report_snapshot_id != snapshot_id:
        raise SnapshotBindingError("Report and PDF snapshot binding does not match")
    if str(report.get("status", "")).casefold() != "approved":
        raise SnapshotBindingError("Only an approved report can be exported")

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=17 * mm,
        rightMargin=17 * mm,
        topMargin=16 * mm,
        bottomMargin=17 * mm,
        title=f"SuperK Franchise — {snapshot.get('report_month', 'Monthly report')}",
        author="GrowthByte Reporting",
    )
    styles = _styles()
    story: list[Any] = [
        Paragraph("SuperK Franchise", styles["ReportTitle"]),
        Paragraph("Unified monthly performance report", styles["ReportSubtitle"]),
        Spacer(1, 5 * mm),
    ]

    metadata = [
        ["Reporting month", _display(snapshot.get("report_month"))],
        ["Vertical", "B2B / Franchise"],
        ["Quality", _display(snapshot.get("quality_status")).title()],
        ["Snapshot", snapshot_id],
        [
            "Snapshot version",
            _display(snapshot.get("snapshot_version") or snapshot.get("version")),
        ],
        ["Formula version", _display(snapshot.get("formula_version"))],
    ]
    story.extend([_table(metadata, widths=[45 * mm, 120 * mm]), Spacer(1, 6 * mm)])

    content = report.get("content") if isinstance(report.get("content"), dict) else report
    story.extend(_claim_section("Executive summary", content.get("executive_summary"), styles))

    metrics = _metric_map(snapshot)
    current_vs_previous = [
        ["Metric", "Current", "Previous", "Change"],
        *[
            [
                _metric_label(key),
                _format_metric(metrics.get(key)),
                _format_previous(metrics.get(key)),
                _format_change(metrics.get(key)),
            ]
            for key in (
                "spend",
                "link_clicks",
                "operational_leads",
                "rtm_leads",
                "cost_per_lead",
                "rtm_conversion_rate",
                "organic_clicks",
                "organic_impressions",
            )
        ],
    ]
    story.extend(
        [
            Paragraph("Current versus previous month", styles["SectionHeading"]),
            _table(current_vs_previous, header=True),
            Spacer(1, 5 * mm),
        ]
    )

    paid = [
        ["Paid performance", "Value"],
        *[
            [_metric_label(key), _format_metric(metrics.get(key))]
            for key in (
                "spend",
                "period_reach",
                "impressions",
                "link_clicks",
                "ctr",
                "cpc",
                "cpm",
            )
        ],
    ]
    funnel = [
        ["Lead and RTM funnel", "Value"],
        *[
            [_metric_label(key), _format_metric(metrics.get(key))]
            for key in (
                "operational_leads",
                "meta_reported_leads",
                "rtm_leads",
                "cost_per_lead",
                "rtm_conversion_rate",
                "cost_per_rtm",
                "click_to_lead_conversion_rate",
            )
        ],
    ]
    story.extend(
        [
            KeepTogether(
                [
                    Paragraph("Paid performance", styles["SectionHeading"]),
                    _table(paid, header=True, widths=[90 * mm, 75 * mm]),
                ]
            ),
            Spacer(1, 5 * mm),
            KeepTogether(
                [
                    Paragraph("Lead and RTM funnel", styles["SectionHeading"]),
                    _table(funnel, header=True, widths=[90 * mm, 75 * mm]),
                ]
            ),
            Spacer(1, 5 * mm),
        ]
    )

    gsc = [
        ["Search Console", "Value"],
        *[
            [_metric_label(key), _format_metric(metrics.get(key))]
            for key in (
                "organic_clicks",
                "organic_impressions",
                "organic_ctr",
                "organic_average_position",
            )
        ],
    ]
    story.extend(
        [
            Paragraph("Search Console SEO summary", styles["SectionHeading"]),
            _table(gsc, header=True, widths=[90 * mm, 75 * mm]),
            Spacer(1, 5 * mm),
        ]
    )

    for title, key in (
        ("Paid-performance summary", "paid_performance_summary"),
        ("Lead and RTM funnel", "lead_and_rtm_funnel"),
        ("Search Console SEO summary", "search_console_seo_summary"),
        (
            "Campaign and creative observations",
            "campaign_and_creative_observations",
        ),
        ("Search query and page movements", "search_query_and_page_movements"),
        ("Important wins", "important_wins"),
        ("Important problems", "important_problems"),
        ("Recommended actions", "recommended_actions"),
        ("Data reconciliation and limitations", "data_reconciliation_and_limitations"),
    ):
        story.extend(_claim_section(title, content.get(key), styles))

    warnings = snapshot.get("quality_reasons") or snapshot.get("quality_warnings") or []
    if warnings:
        story.extend(_text_list("Data limitations", warnings, styles))

    story.extend(
        [
            PageBreak(),
            Paragraph("Evidence references", styles["SectionHeading"]),
            *_evidence_paragraphs(snapshot.get("evidence") or [], styles),
        ]
    )
    document.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "ReportTitle": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=25,
            leading=29,
            textColor=TEAL,
            alignment=TA_CENTER,
        ),
        "ReportSubtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontSize=11,
            leading=15,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
        "SectionHeading": ParagraphStyle(
            "SectionHeading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=TEAL,
            spaceBefore=4,
            spaceAfter=6,
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontSize=9.5,
            leading=14,
            textColor=INK,
            spaceAfter=4,
        ),
        "Evidence": ParagraphStyle(
            "Evidence",
            parent=base["BodyText"],
            fontName="Courier",
            fontSize=6.8,
            leading=9,
            textColor=MUTED,
            wordWrap="CJK",
        ),
    }


def _table(
    rows: list[list[str]],
    *,
    header: bool = False,
    widths: list[float] | None = None,
) -> Table:
    safe_rows = [[Paragraph(escape(str(cell)), _cell_style()) for cell in row] for row in rows]
    table = Table(safe_rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    rules: list[tuple[Any, ...]] = [
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D5D5D5")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        rules.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TEAL),
                ("TEXTCOLOR", (0, 0), (-1, 0), PAPER),
            ]
        )
    table.setStyle(TableStyle(rules))
    return table


def _cell_style() -> ParagraphStyle:
    return ParagraphStyle("Cell", fontName="Helvetica", fontSize=8.5, leading=11, textColor=INK)


def _summary_section(title: str, value: Any, styles: dict[str, ParagraphStyle]) -> list[Any]:
    return [
        Paragraph(title, styles["SectionHeading"]),
        Paragraph(escape(_display(value)), styles["Body"]),
        Spacer(1, 4 * mm),
    ]


def _claim_section(title: str, value: Any, styles: dict[str, ParagraphStyle]) -> list[Any]:
    if isinstance(value, str):
        return _summary_section(title, value, styles)
    items = value if isinstance(value, list) else []
    rendered: list[Any] = [Paragraph(title, styles["SectionHeading"])]
    if not items:
        rendered.append(Paragraph("Unavailable.", styles["Body"]))
    for index, item in enumerate(items, 1):
        statement = item.get("statement") if isinstance(item, dict) else item
        rendered.append(Paragraph(f"{index}. {escape(_display(statement))}", styles["Body"]))
    rendered.append(Spacer(1, 4 * mm))
    return rendered


def _text_list(title: str, values: Any, styles: dict[str, ParagraphStyle]) -> list[Any]:
    rendered: list[Any] = [Paragraph(title, styles["SectionHeading"])]
    for value in values if isinstance(values, list) else []:
        rendered.append(Paragraph(f"• {escape(_display(value))}", styles["Body"]))
    rendered.append(Spacer(1, 4 * mm))
    return rendered


def _metric_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metrics = snapshot.get("metrics") or snapshot.get("snapshot_data", {}).get("metrics") or []
    return {
        str(metric.get("metric_key")): metric
        for metric in metrics
        if isinstance(metric, dict) and metric.get("metric_key")
    }


def _format_metric(metric: dict[str, Any] | None) -> str:
    if not metric or metric.get("value") is None:
        return "Unavailable."
    value = float(metric["value"])
    unit = metric.get("unit")
    if unit == "currency":
        return f"{metric.get('currency') or 'INR'} {value:,.2f}"
    if unit == "percent":
        return f"{value:,.2f}%"
    if unit == "position":
        return f"{value:,.2f}"
    return f"{value:,.0f}"


def _format_previous(metric: dict[str, Any] | None) -> str:
    if not metric or metric.get("previous_value") is None:
        return "Unavailable."
    copy = dict(metric)
    copy["value"] = metric["previous_value"]
    return _format_metric(copy)


def _format_change(metric: dict[str, Any] | None) -> str:
    if not metric or metric.get("percentage_change") is None:
        return "Unavailable."
    return f"{float(metric['percentage_change']):+,.2f}%"


def _metric_label(key: str) -> str:
    return {
        "spend": "Amount spent",
        "period_reach": "Reach",
        "impressions": "Impressions",
        "link_clicks": "Link clicks",
        "ctr": "CTR",
        "cpc": "CPC",
        "cpm": "CPM",
        "operational_leads": "Total leads",
        "meta_reported_leads": "Meta-reported leads",
        "rtm_leads": "RTM leads",
        "cost_per_lead": "Cost per lead",
        "rtm_conversion_rate": "RTM conversion",
        "cost_per_rtm": "Cost per RTM",
        "click_to_lead_conversion_rate": "Click-to-lead conversion",
        "organic_clicks": "Organic clicks",
        "organic_impressions": "Organic impressions",
        "organic_ctr": "Search CTR",
        "organic_average_position": "Average position",
    }.get(key, key.replace("_", " ").title())


def _display(value: Any) -> str:
    if value is None or value == "":
        return "Unavailable."
    return str(value)


def _evidence_paragraphs(evidence: Any, styles: dict[str, ParagraphStyle]) -> list[Paragraph]:
    if not isinstance(evidence, list) or not evidence:
        return [Paragraph("Unavailable.", styles["Body"])]
    return [
        Paragraph(
            escape(
                f"{item.get('evidence_id', 'Unavailable.')} — "
                f"{item.get('metric_key', 'metric')}: {_display(item.get('metric_value'))}"
            ),
            styles["Evidence"],
        )
        for item in evidence
        if isinstance(item, dict)
    ]


def _page_footer(canvas: Any, document: Any) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(17 * mm, 9 * mm, "GrowthByte Reporting • SuperK Franchise")
    canvas.drawRightString(A4[0] - 17 * mm, 9 * mm, f"Page {document.page}")
    canvas.restoreState()
