import json

import httpx
import pytest
from pydantic import SecretStr

from app.agent.skills.superk_franchise_monthly_report.prompt import build_superk_prompt
from app.agent.superk_glm import SuperKAgentError, SuperKGLMClient


def _bundle() -> dict[str, object]:
    evidence_id = "metric_snapshot:11111111-1111-1111-1111-111111111111:spend"
    return {
        "client": {"name": "SuperK"},
        "vertical": "b2b_franchise",
        "report_month": "2026-07",
        "snapshot_id": "11111111-1111-1111-1111-111111111111",
        "formula_version": "superk-franchise-2026-08-v1",
        "quality_status": "partial",
        "quality_warnings": [],
        "evidence": [
            {
                "evidence_id": evidence_id,
                "metric_value": "754590.54",
                "unit": "currency",
            }
        ],
        "evidence_ids": [evidence_id],
    }


def test_prompt_redacts_pii_and_secret_fields() -> None:
    prompt = build_superk_prompt(
        evidence_bundle=_bundle(),
        approved_knowledge=[
            {
                "id": "knowledge-1",
                "category": "context",
                "knowledge_key": "sensitive-test",
                "value": {
                    "summary": "Call +91 98765 43210 or owner@example.com",
                    "access_token": "must-not-cross-boundary",
                    "lead_rows": [{"lead_name": "Private Person"}],
                    "customer_name": "Jane Smith",
                    "api_key": "must-also-not-cross-boundary",
                },
                "version": 1,
            }
        ],
    )

    assert "owner@example.com" not in prompt
    assert "98765 43210" not in prompt
    assert "must-not-cross-boundary" not in prompt
    assert "Private Person" not in prompt
    assert "Jane Smith" not in prompt
    assert "must-also-not-cross-boundary" not in prompt
    assert "[REDACTED_EMAIL]" in prompt
    assert "[REDACTED_PHONE]" in prompt
    assert "754590.54" in prompt


def test_prompt_projects_only_approved_knowledge_fields() -> None:
    prompt = build_superk_prompt(
        evidence_bundle=_bundle(),
        approved_knowledge=[
            {
                "id": "knowledge-1",
                "category": "context",
                "knowledge_key": "franchise_offer",
                "value": {"summary": "Approved summary"},
                "version": 2,
                "source_reference": "must-not-cross-boundary",
                "approved_by_label": "Private Approver",
            }
        ],
    )

    assert "Approved summary" in prompt
    assert "must-not-cross-boundary" not in prompt
    assert "Private Approver" not in prompt


@pytest.mark.asyncio
async def test_glm_client_parses_fenced_report_json_without_logging_raw_response() -> None:
    claim = {
        "statement": "Verified summary.",
        "evidence_ids": ["metric_snapshot:11111111-1111-1111-1111-111111111111:spend"],
        "confidence": "high",
    }
    report = {
        "executive_summary": [claim],
        "paid_performance_summary": [claim],
        "lead_and_rtm_funnel": [claim],
        "search_console_seo_summary": [claim],
        "campaign_and_creative_observations": [claim],
        "search_query_and_page_movements": [claim],
        "important_wins": [claim],
        "important_problems": [claim],
        "recommended_actions": [claim],
        "data_reconciliation_and_limitations": [claim],
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        request_body = json.loads(request.content)
        assert request.headers["Authorization"] == "Bearer synthetic-secret"
        assert request_body["model"] == "test-model"
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": f"```json\n{json.dumps(report)}\n```"}]},
        )

    client = SuperKGLMClient(
        base_url="https://glm.invalid",
        auth_token=SecretStr("synthetic-secret"),
        model="test-model",
        transport=httpx.MockTransport(handler),
    )
    try:
        output, metadata = await client.generate_report(
            evidence_bundle=_bundle(),
            approved_knowledge=[],
        )
    finally:
        await client.close()

    assert output == report
    assert metadata["prompt_version"] == "superk-franchise-monthly-2026-08-v1"


@pytest.mark.asyncio
async def test_glm_client_uses_safe_error_for_provider_failure() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "secret provider detail"}})

    client = SuperKGLMClient(
        base_url="https://glm.invalid",
        auth_token=SecretStr("synthetic-secret"),
        model="test-model",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(SuperKAgentError) as exc_info:
            await client.generate_report(evidence_bundle=_bundle(), approved_knowledge=[])
    finally:
        await client.close()

    assert exc_info.value.code == "glm_unavailable"
    assert "secret provider detail" not in str(exc_info.value)
    assert "synthetic-secret" not in str(exc_info.value)
