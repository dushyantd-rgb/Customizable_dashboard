from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class MappingDisposition(StrEnum):
    MAPPED = "mapped"
    IGNORED = "ignored"
    UNRESOLVED = "unresolved"


class FieldClassification(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_table: str
    source_field: str
    target_field: str | None
    disposition: MappingDisposition
    reason: str


class KnowledgeImportPreview(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_record_count: int
    mapped_record_count: int
    ignored_record_count: int
    unresolved_record_count: int
    field_classification: tuple[FieldClassification, ...]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]
    writes_performed: Literal[0] = 0


class KnowledgeImportResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_record_count: int
    upserted_record_count: int
    deleted_record_count: Literal[0] = 0
    knowledge_source_write_count: Literal[0] = 0
    conflict_target: tuple[str, str, str, str] = (
        "client_id",
        "source_type",
        "source_identifier",
        "source_version",
    )


@dataclass(frozen=True)
class SourceClient:
    identifier: str


@dataclass(frozen=True)
class SourceKnowledgeRecord:
    table: str
    fields: dict[str, Any]


@dataclass(frozen=True)
class MappedKnowledgeRecord:
    category: str
    knowledge_key: str
    value: dict[str, Any]
    status: str
    source_type: str
    source_identifier: str
    source_display_name: str | None
    source_reference: str
    source_version: str
    source_hash: str
    version: int


@dataclass(frozen=True)
class MappingResult:
    source_record_count: int
    records: tuple[MappedKnowledgeRecord, ...]
    ignored_record_count: int
    unresolved_record_count: int
    field_classification: tuple[FieldClassification, ...]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]
