from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClientSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str


class ClientDetails(ClientSummary):
    reporting_timezone: str
    default_currency: str
    created_at: datetime
    updated_at: datetime


class KnowledgeRecord(BaseModel):
    id: UUID
    client_id: UUID
    category: str
    knowledge_key: str
    value: dict[str, Any]
    status: str
    source_type: str
    source_identifier: str | None
    source_display_name: str | None
    source_reference: str | None
    source_version: str | None
    imported_at: datetime | None
    version: int
    approved_by_label: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class KnowledgeCreate(_InputModel):
    category: str
    knowledge_key: str
    value: dict[str, Any]
    status: str

    @field_validator("category", "knowledge_key", "status")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value must not be blank")
        return normalized


class KnowledgeUpdate(_InputModel):
    category: str | None = None
    knowledge_key: str | None = None
    value: dict[str, Any] | None = None
    status: str | None = None

    @field_validator("category", "knowledge_key", "status")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Editable text fields cannot be null")
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value must not be blank")
        return normalized

    @field_validator("value")
    @classmethod
    def reject_null_value(cls, value: dict[str, Any] | None) -> dict[str, Any]:
        if value is None:
            raise ValueError("Knowledge value cannot be null")
        return value

    @model_validator(mode="after")
    def require_change(self) -> "KnowledgeUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one editable field is required")
        return self


class KpiRecord(BaseModel):
    id: UUID
    client_id: UUID
    metric_key: str
    label: str
    target_value: Decimal | None
    unit: str
    direction: str
    attribution_level: str
    active_from: date
    active_to: date | None
    created_at: datetime
    updated_at: datetime


class KpiCreate(_InputModel):
    metric_key: str
    label: str = Field(max_length=120)
    target_value: Decimal | None = None
    unit: str
    direction: str
    attribution_level: str
    active_from: date
    active_to: date | None = None

    @field_validator("metric_key", "label", "unit", "direction", "attribution_level")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value must not be blank")
        return normalized

    @field_validator("target_value")
    @classmethod
    def require_finite_target(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("Target value must be finite")
        return value

    @model_validator(mode="after")
    def validate_interval(self) -> "KpiCreate":
        if self.active_to is not None and self.active_to < self.active_from:
            raise ValueError("Active-to date must not precede active-from date")
        return self


class KpiUpdate(_InputModel):
    metric_key: str | None = None
    label: str | None = Field(default=None, max_length=120)
    target_value: Decimal | None = None
    unit: str | None = None
    direction: str | None = None
    attribution_level: str | None = None
    active_from: date | None = None
    active_to: date | None = None

    @field_validator("metric_key", "label", "unit", "direction", "attribution_level")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Required KPI fields cannot be null")
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value must not be blank")
        return normalized

    @field_validator("active_from")
    @classmethod
    def reject_null_active_from(cls, value: date | None) -> date:
        if value is None:
            raise ValueError("Active-from date cannot be null")
        return value

    @field_validator("target_value")
    @classmethod
    def require_finite_target(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("Target value must be finite")
        return value

    @model_validator(mode="after")
    def require_change(self) -> "KpiUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one editable field is required")
        return self


class SafeErrorDetail(BaseModel):
    location: tuple[str | int, ...]
    code: str
    message: str


class SafeErrorBody(BaseModel):
    code: str
    message: str
    details: tuple[SafeErrorDetail, ...] = ()


class SafeErrorResponse(BaseModel):
    error: SafeErrorBody
