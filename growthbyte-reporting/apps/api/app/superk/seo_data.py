"""SEO data loading and validation for SuperK Franchise reports.

This module handles loading and validating SEO milestone and cache data from JSON files.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SeoMilestone(BaseModel):
    """A single SEO milestone event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: str
    source: str
    title: str
    payload: str
    dedup_key: str
    occurred_at: datetime
    created_at: datetime


class SeoMilestoneCollection(BaseModel):
    """Collection of SEO milestones."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    milestones: tuple[SeoMilestone, ...]

    @property
    def milestone_count(self) -> int:
        return len(self.milestones)


class SeoQueryRow(BaseModel):
    """A single query row from SEO cache."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    clicks: int | None = None
    impressions: int | None = None
    ctr: float | None = None
    position: float | None = None

    # Previous period data
    prev_clicks: int | None = Field(default=None, alias="prev_clicks")
    prev_impressions: int | None = Field(default=None, alias="prev_impressions")
    prev_ctr: float | None = Field(default=None, alias="prev_ctr")
    prev_position: float | None = Field(default=None, alias="prev_position")


class SeoCacheEntry(BaseModel):
    """A single SEO cache entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    organization_id: str
    client_id: str
    report_kind: str
    params_hash: str
    range_start: str
    range_end: str
    payload: str  # JSON string containing rows

    def parse_rows(self) -> list[dict[str, Any]]:
        """Parse the payload JSON into row data."""
        try:
            data = json.loads(self.payload)
            return data.get("rows", [])
        except json.JSONDecodeError:
            return []


SeoSourceClassification = Literal[
    "valid_seo_cache",
    "invalid_json",
    "payload_too_large",
    "source_unavailable",
]


class SeoCacheInspection(BaseModel):
    """Result of inspecting SEO cache source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    classification: SeoSourceClassification
    payload_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    entry_count: int = 0
    query_count: int = 0


def inspect_seo_cache(source: bytes | bytearray | Path | str) -> SeoCacheInspection:
    """Inspect SEO cache data.

    Args:
        source: Path to SEO cache file or raw bytes/string data

    Returns:
        SeoCacheInspection with classification and metadata
    """
    MAX_SOURCE_BYTES = 10 * 1024 * 1024  # 10 MB

    if isinstance(source, Path | str):
        path = Path(source)
        try:
            payload = path.read_bytes()
        except OSError:
            return SeoCacheInspection(classification="source_unavailable")
    else:
        payload = bytes(source)

    if len(payload) > MAX_SOURCE_BYTES:
        return SeoCacheInspection(
            classification="payload_too_large",
            payload_hash=hashlib.sha256(payload).hexdigest(),
        )

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return SeoCacheInspection(
            classification="invalid_json",
            payload_hash=hashlib.sha256(payload).hexdigest(),
        )

    payload_hash = hashlib.sha256(payload).hexdigest()

    if not isinstance(parsed, list):
        return SeoCacheInspection(
            classification="invalid_json",
            payload_hash=payload_hash,
        )

    total_queries = 0
    for entry in parsed:
        if isinstance(entry, dict) and "payload" in entry:
            try:
                payload_data = json.loads(entry.get("payload", "{}"))
                rows = payload_data.get("rows", [])
                total_queries += len(rows)
            except json.JSONDecodeError:
                pass

    return SeoCacheInspection(
        classification="valid_seo_cache",
        payload_hash=payload_hash,
        entry_count=len(parsed),
        query_count=total_queries,
    )


def load_seo_data(path: Path) -> SeoMilestoneCollection | None:
    """Load SEO milestone data from JSON file.

    Args:
        path: Path to SEO data JSON file

    Returns:
        SeoMilestoneCollection if valid, None otherwise
    """
    try:
        payload = path.read_bytes()
        parsed = json.loads(payload)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(parsed, list):
        return None

    try:
        milestones = tuple(SeoMilestone.model_validate(item) for item in parsed)
        return SeoMilestoneCollection(milestones=milestones)
    except Exception:
        return None


def load_seo_cache(path: Path) -> list[SeoCacheEntry] | None:
    """Load SEO cache entries from JSON file.

    Args:
        path: Path to SEO cache file

    Returns:
        List of SeoCacheEntry if valid, None otherwise
    """
    try:
        payload = path.read_bytes()
        parsed = json.loads(payload)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(parsed, list):
        return None

    try:
        return [SeoCacheEntry.model_validate(item) for item in parsed]
    except Exception:
        return None


def extract_top_queries(
    entries: list[SeoCacheEntry],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Extract top queries by clicks from SEO cache entries.

    Args:
        entries: List of SEO cache entries
        limit: Maximum number of queries to return

    Returns:
        List of query dictionaries with clicks, impressions, ctr, position
    """
    all_rows: list[dict[str, Any]] = []
    for entry in entries:
        rows = entry.parse_rows()
        all_rows.extend(rows)

    # Sort by clicks descending
    sorted_rows = sorted(
        all_rows,
        key=lambda r: r.get("clicks", 0) or 0,
        reverse=True,
    )

    return sorted_rows[:limit]
