"""Pydantic models for Meta Graph API requests and responses."""

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MetaAdAccountSummary(BaseModel):
    """Summary of a Meta ad account accessible through the Graph API."""

    model_config = ConfigDict(extra="forbid")

    external_account_id: str = Field(..., min_length=1)
    name: str | None = None
    currency: str | None = None
    account_timezone: str | None = None
    account_status: str | None = None


class MetaCampaignSummary(BaseModel):
    """Summary of a Meta campaign."""

    model_config = ConfigDict(extra="forbid")

    external_campaign_id: str = Field(..., min_length=1)
    name: str | None = None
    objective: str | None = None
    status: str | None = None
    effective_status: str | None = None


class MetaAdSetSummary(BaseModel):
    """Summary of a Meta ad set."""

    model_config = ConfigDict(extra="forbid")

    external_ad_set_id: str = Field(..., min_length=1)
    external_campaign_id: str | None = None
    name: str | None = None
    status: str | None = None
    effective_status: str | None = None


class MetaAdSummary(BaseModel):
    """Summary of a Meta ad."""

    model_config = ConfigDict(extra="forbid")

    external_ad_id: str = Field(..., min_length=1)
    external_ad_set_id: str | None = None
    name: str | None = None
    creative_id: str | None = None
    status: str | None = None
    effective_status: str | None = None


class MetaInsightRow(BaseModel):
    """Single row from Meta Insights API."""

    model_config = ConfigDict(extra="allow")

    date_start: str
    date_stop: str
    account_id: str
    campaign_id: str | None = None
    adset_id: str | None = None
    ad_id: str | None = None
    impressions: str = "0"
    reach: str = "0"
    clicks: str = "0"
    inline_link_clicks: str = "0"
    spend: str = "0"
    actions: list[dict[str, Any]] = Field(default_factory=list)
    action_values: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("impressions", "reach", "clicks", "inline_link_clicks", mode="before")
    @classmethod
    def normalize_string_counts(cls, value: str | int | None) -> str:
        if value is None:
            return "0"
        return str(value)

    @field_validator("spend", mode="before")
    @classmethod
    def normalize_spend(cls, value: str | int | float | Decimal | None) -> str:
        if value is None:
            return "0"
        return str(value)


class MetaInsightRequest(BaseModel):
    """Request parameters for Meta Insights API."""

    model_config = ConfigDict(extra="forbid")

    external_account_id: str = Field(..., min_length=1)
    date_from: date
    date_to: date
    level: str = Field(default="account", pattern="^(account|campaign|adset|ad)$")
    fields: list[str] = Field(
        default_factory=lambda: [
            "account_id",
            "campaign_id",
            "adset_id",
            "ad_id",
            "impressions",
            "reach",
            "clicks",
            "inline_link_clicks",
            "spend",
            "actions",
            "action_values",
            "date_start",
            "date_stop",
        ]
    )
    time_increment: int = Field(default=1, description="Day granularity")
    limit: int = Field(default=100, ge=1, le=1000)


class MetaConnectionConfig(BaseModel):
    """Configuration for a Meta connection to a specific client."""

    model_config = ConfigDict(extra="forbid")

    external_account_id: str = Field(..., min_length=1)
    display_name: str | None = None


class MetaSyncRequest(BaseModel):
    """Request to manually sync Meta data."""

    model_config = ConfigDict(extra="forbid")

    date_from: date
    date_to: date
    include_campaigns: bool = Field(default=True)
    include_ad_sets: bool = Field(default=True)
    include_ads: bool = Field(default=True)
    include_insights: bool = Field(default=True)

    @field_validator("date_to")
    @classmethod
    def validate_date_range(cls, value: date, info: Any) -> date:
        date_from = info.data.get("date_from")
        if date_from is not None and value < date_from:
            raise ValueError("date_to must not precede date_from")
        return value


class MetaAccountDiscoveryResponse(BaseModel):
    """Response for Meta account discovery."""

    model_config = ConfigDict(extra="forbid")

    accounts: list[MetaAdAccountSummary]


class MetaSyncResult(BaseModel):
    """Result of a Meta sync operation."""

    model_config = ConfigDict(extra="forbid")

    sync_run_id: str
    client_id: str
    external_account_id: str
    status: str
    rows_read: int
    rows_written: int
    warning_count: int = 0
    campaigns_synced: int
    ad_sets_synced: int
    ads_synced: int
    insights_synced: int
    error_summary: str | None = None
