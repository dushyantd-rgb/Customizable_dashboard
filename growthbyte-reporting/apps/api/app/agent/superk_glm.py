"""Secret-safe Anthropic-compatible client for the SuperK reporting skill."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import SecretStr

from app.agent.skills.superk_franchise_monthly_report import (
    PROMPT_VERSION,
    build_superk_prompt,
    build_superk_system_prompt,
)


class SuperKAgentError(Exception):
    """Safe agent error whose message contains no provider response or credential."""

    def __init__(self, code: str, safe_message: str) -> None:
        self.code = code
        self.safe_message = safe_message
        super().__init__(safe_message)


class SuperKGLMClient:
    """Small Phase-5-compatible GLM transport with bounded retry behavior."""

    def __init__(
        self,
        *,
        base_url: str,
        auth_token: SecretStr,
        model: str,
        timeout_seconds: float = 90.0,
        max_retries: int = 1,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        self._max_retries = max(0, max_retries)
        self._auth_token = auth_token
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds, connect=10.0),
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def generate_report(
        self,
        *,
        evidence_bundle: dict[str, Any],
        approved_knowledge: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return parsed JSON and non-sensitive generation metadata."""

        started_at = datetime.now(UTC)
        payload = {
            "model": self._model,
            "max_tokens": 4096,
            "system": build_superk_system_prompt(),
            "messages": [
                {
                    "role": "user",
                    "content": build_superk_prompt(
                        evidence_bundle=evidence_bundle,
                        approved_knowledge=approved_knowledge,
                    ),
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._auth_token.get_secret_value()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post("/v1/messages", json=payload, headers=headers)
            except httpx.TimeoutException as error:
                if attempt < self._max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                raise SuperKAgentError("glm_timeout", "Report generation timed out") from error
            except httpx.TransportError as error:
                if attempt < self._max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                raise SuperKAgentError(
                    "glm_unavailable", "Report generation service is unavailable"
                ) from error

            if response.status_code >= 500 and attempt < self._max_retries:
                await asyncio.sleep(2**attempt)
                continue
            if response.status_code >= 400:
                raise SuperKAgentError("glm_unavailable", "Report generation request failed")

            try:
                provider_payload = response.json()
                output = _extract_json(provider_payload)
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                raise SuperKAgentError(
                    "invalid_json", "Report generation returned invalid JSON"
                ) from error

            finished_at = datetime.now(UTC)
            return output, {
                "model_alias": self._model,
                "prompt_version": PROMPT_VERSION,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            }

        raise SuperKAgentError("glm_unavailable", "Report generation service is unavailable")


def _extract_json(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("response must be an object")
    if _looks_like_report(payload):
        return payload

    content = payload.get("content")
    text = ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                value = block.get("text")
                if isinstance(value, str):
                    parts.append(value)
        text = "".join(parts)
    if not text.strip():
        raise ValueError("response did not contain text")

    normalized = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", normalized, flags=re.DOTALL)
    if fenced:
        normalized = fenced.group(1)
    decoded = json.loads(normalized)
    if not isinstance(decoded, dict):
        raise ValueError("report must be an object")
    return decoded


def _looks_like_report(payload: dict[str, Any]) -> bool:
    return "executive_summary" in payload and "recommended_actions" in payload
