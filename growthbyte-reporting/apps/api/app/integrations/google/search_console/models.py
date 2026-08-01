"""Strict models for Google Search Console discovery and Search Analytics data."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SearchConsoleProperty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_url: str = Field(min_length=1)
    permission_level: str | None = None


class SearchConsoleMetricRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keys: tuple[str, ...] = ()
    clicks: Decimal | None = None
    impressions: Decimal | None = None
    ctr: Decimal | None = None
    average_position: Decimal | None = None


class SearchConsoleQueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: tuple[SearchConsoleMetricRow, ...] = ()
    response_aggregation_type: str | None = None


class SearchConsoleSyncResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sync_run_id: str
    client_id: str
    site_url: str
    period_start: date
    period_end: date
    status: str
    totals_written: int
    query_rows_written: int
    page_rows_written: int
    warnings: tuple[str, ...] = ()
