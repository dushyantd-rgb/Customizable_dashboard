"""Versioned prompt construction for the SuperK Franchise monthly report."""

from __future__ import annotations

import json
import re
from typing import Any

PROMPT_VERSION = "superk-franchise-monthly-2026-08-v1"

_REQUIRED_SECTIONS = (
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

_SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "auth_token",
        "client_secret",
        "contact_name",
        "customer_name",
        "email",
        "email_address",
        "first_name",
        "full_name",
        "last_name",
        "lead_name",
        "lead_rows",
        "password",
        "person_name",
        "phone",
        "phone_number",
        "raw_leads",
        "raw_rows",
        "refresh_token",
        "secret",
        "secret_key",
        "service_role_key",
    }
)
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_DECIMAL_STRING_PATTERN = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")
_EVIDENCE_NUMERIC_KEYS = frozenset(
    {
        "absolute_change",
        "denominator",
        "kpi_target",
        "kpi_variance",
        "metric_value",
        "numerator",
        "percentage_change",
        "previous_value",
        "value",
    }
)
_APPROVED_KNOWLEDGE_KEYS = (
    "id",
    "category",
    "knowledge_key",
    "value",
    "version",
)


def build_superk_system_prompt() -> str:
    """Return the immutable policy portion of the reporting prompt."""

    return f"""You generate one SuperK Franchise monthly report.
Prompt version: {PROMPT_VERSION}
Client and vertical are fixed by the application; vertical must be b2b_franchise.

The supplied evidence already contains every calculated metric. Do not calculate, estimate,
repair, interpolate, or invent a number. Never turn missing data into zero. Every numeric claim
must cite one or more supplied evidence IDs containing that exact metric, comparison, or KPI.
Use only approved knowledge supplied in the request. Never output names, email addresses, phone
numbers, raw lead rows, credentials, or access tokens. Do not assert causation or attribution.
Label recommendations as tests unless direct evidence supports the mechanism. A result may be
called improved/declined only when comparison evidence says so, and good/bad only when KPI
evidence says so.

Return only valid JSON with exactly these top-level keys:
{json.dumps(_REQUIRED_SECTIONS)}
Every top-level value must be a non-empty JSON array of claim objects. Each claim object must
contain statement, evidence_ids, and confidence (high, medium, or low), with limitation as the
only optional field. Do not return a bare string for any section and do not add fields.
"""


def build_superk_prompt(
    *,
    evidence_bundle: dict[str, Any],
    approved_knowledge: list[dict[str, Any]],
) -> str:
    """Serialize the allowlisted aggregate input without raw source rows or secrets."""

    payload = _redact_pii(
        {
            "prompt_version": PROMPT_VERSION,
            "vertical": evidence_bundle.get("vertical"),
            "report_month": evidence_bundle.get("report_month"),
            "snapshot_id": evidence_bundle.get("snapshot_id"),
            "formula_version": evidence_bundle.get("formula_version"),
            "quality_status": evidence_bundle.get("quality_status"),
            "quality_warnings": evidence_bundle.get("quality_warnings", []),
            "evidence": evidence_bundle.get("evidence", []),
            "evidence_ids": evidence_bundle.get("evidence_ids", []),
            "approved_knowledge": _project_approved_knowledge(approved_knowledge),
        }
    )
    return (
        "Write the unified monthly report from this aggregate evidence. "
        "Each section must be a non-empty array. Claim objects must contain statement, "
        "evidence_ids, confidence, and optional limitation. "
        "Narrative without a number may cite the most relevant evidence; every statement with a "
        "number must cite evidence containing that number. Return JSON only.\n\n"
        + json.dumps(payload, default=str, ensure_ascii=False, sort_keys=True)
    )


def _project_approved_knowledge(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only narrative fields explicitly approved for the model boundary."""

    return [
        {key: item[key] for key in _APPROVED_KNOWLEDGE_KEYS if key in item}
        for item in items
        if isinstance(item, dict)
    ]


def _redact_pii(
    value: Any,
    *,
    key: str | None = None,
    evidence_context: bool = False,
) -> Any:
    """Defence-in-depth redaction before any data crosses the model boundary."""

    if key is not None and key.casefold() in _SENSITIVE_KEYS:
        return "[REDACTED]"
    inside_evidence = evidence_context or (key is not None and key.casefold() == "evidence")
    if isinstance(value, dict):
        return {
            str(item_key): _redact_pii(
                item,
                key=str(item_key),
                evidence_context=inside_evidence,
            )
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_pii(item, evidence_context=inside_evidence) for item in value]
    if isinstance(value, tuple):
        return [_redact_pii(item, evidence_context=inside_evidence) for item in value]
    if isinstance(value, str):
        if (
            inside_evidence
            and key is not None
            and key.casefold() in _EVIDENCE_NUMERIC_KEYS
            and _DECIMAL_STRING_PATTERN.fullmatch(value.strip())
        ):
            return value
        redacted = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
        return _PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)
    return value
