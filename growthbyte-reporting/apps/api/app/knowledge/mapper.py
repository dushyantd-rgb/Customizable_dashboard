import hashlib
import json
from typing import Any

from app.knowledge.models import (
    FieldClassification,
    MappedKnowledgeRecord,
    MappingDisposition,
    MappingResult,
    SourceKnowledgeRecord,
)

_SECTION_TABLE = "org_knowledge_base_sections"
_ITEM_TABLE = "org_knowledge_items"


class KnowledgeMapper:
    def map(
        self,
        *,
        source_records: tuple[SourceKnowledgeRecord, ...],
        target_status: str | None,
    ) -> MappingResult:
        normalized_status = target_status.strip() if target_status else None
        records: list[MappedKnowledgeRecord] = []
        warnings: list[str] = []
        blockers: list[str] = []
        ignored_count = 0
        ignored_item_count = 0
        empty_section_count = 0
        unresolved_count = 0

        if not source_records:
            warnings.append("no_source_knowledge")

        if not normalized_status:
            blockers.append("target_status_required")

        for source_record in source_records:
            if source_record.table == _ITEM_TABLE:
                ignored_count += 1
                ignored_item_count += 1
                continue
            if source_record.table != _SECTION_TABLE:
                unresolved_count += 1
                blockers.append("unsupported_source_table")
                continue

            if _is_empty_section(source_record.fields) and _has_required_section_identity(
                source_record.fields
            ):
                ignored_count += 1
                empty_section_count += 1
                continue

            mapped_record = self._map_section(
                source_record.fields,
                target_status=normalized_status or "",
            )
            if mapped_record is None:
                unresolved_count += 1
                blockers.append("missing_required_section_fields")
                continue
            records.append(mapped_record)

        if ignored_item_count:
            warnings.append("knowledge_items_excluded_pending_contract_approval")
        if empty_section_count:
            warnings.append("empty_knowledge_sections_excluded")
        if not records:
            blockers.append("no_importable_knowledge")

        collision_keys = [
            (record.category, record.knowledge_key, record.version) for record in records
        ]
        if len(collision_keys) != len(set(collision_keys)):
            blockers.append("target_semantic_version_collision")

        return MappingResult(
            source_record_count=len(source_records),
            records=tuple(records),
            ignored_record_count=ignored_count,
            unresolved_record_count=unresolved_count,
            field_classification=_field_classification(),
            warnings=tuple(dict.fromkeys(warnings)),
            blockers=tuple(dict.fromkeys(blockers)),
        )

    @staticmethod
    def _map_section(row: dict[str, Any], *, target_status: str) -> MappedKnowledgeRecord | None:
        source_identifier = _nonempty_string(row.get("id"))
        section_key = _nonempty_string(row.get("section_key"))
        version = _positive_integer(row.get("version"))
        title = _optional_string(row.get("title"))
        content = row.get("content")
        structured_data = row.get("structured_data")

        if (
            source_identifier is None
            or section_key is None
            or version is None
            or not _has_knowledge_value(content, structured_data)
        ):
            return None

        value = {
            "title": title,
            "content": content,
            "structured_data": structured_data,
            "section_number": row.get("section_number"),
        }
        canonical_value = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return MappedKnowledgeRecord(
            category=section_key,
            knowledge_key=section_key,
            value=value,
            status=target_status,
            source_type="knowledge_supabase_section",
            source_identifier=source_identifier,
            source_display_name=title,
            source_reference=_SECTION_TABLE,
            source_version=str(version),
            source_hash=hashlib.sha256(canonical_value.encode("utf-8")).hexdigest(),
            version=version,
        )


def _field_classification() -> tuple[FieldClassification, ...]:
    mapped = MappingDisposition.MAPPED
    ignored = MappingDisposition.IGNORED
    unresolved = MappingDisposition.UNRESOLVED
    return (
        FieldClassification(
            source_table=_SECTION_TABLE,
            source_field="id",
            target_field="source_identifier",
            disposition=mapped,
            reason="stable source row identity",
        ),
        FieldClassification(
            source_table=_SECTION_TABLE,
            source_field="section_key",
            target_field="category,knowledge_key",
            disposition=mapped,
            reason="stable semantic section key",
        ),
        FieldClassification(
            source_table=_SECTION_TABLE,
            source_field="title,content,structured_data,section_number",
            target_field="value",
            disposition=mapped,
            reason="preserved section payload",
        ),
        FieldClassification(
            source_table=_SECTION_TABLE,
            source_field="title",
            target_field="source_display_name",
            disposition=mapped,
            reason="non-identity display metadata",
        ),
        FieldClassification(
            source_table=_SECTION_TABLE,
            source_field="version",
            target_field="source_version,version",
            disposition=mapped,
            reason="explicit source version",
        ),
        FieldClassification(
            source_table=_SECTION_TABLE,
            source_field="client_id",
            target_field=None,
            disposition=ignored,
            reason="source scope only; target client is always explicit",
        ),
        FieldClassification(
            source_table=_SECTION_TABLE,
            source_field="approvals,created_at,updated_at",
            target_field=None,
            disposition=ignored,
            reason="review identity and timestamps are outside the approved import contract",
        ),
        FieldClassification(
            source_table=_ITEM_TABLE,
            source_field="id,title,content,content_type,tags",
            target_field=None,
            disposition=unresolved,
            reason="knowledge-item subset and source-version rule are not approved",
        ),
        FieldClassification(
            source_table="operator",
            source_field="target_status",
            target_field="status",
            disposition=mapped,
            reason="explicit apply-time value; no status is inferred",
        ),
    )


def _nonempty_string(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return _nonempty_string(value)


def _positive_integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 1:
        return value
    if isinstance(value, str) and value.isdigit() and int(value) >= 1:
        return int(value)
    return None


def _has_knowledge_value(content: Any, structured_data: Any) -> bool:
    content_present = content is not None and (
        not isinstance(content, str) or bool(content.strip())
    )
    structured_present = structured_data not in (None, {}, [], "")
    return content_present or structured_present


def _is_empty_section(row: dict[str, Any]) -> bool:
    return not _has_knowledge_value(row.get("content"), row.get("structured_data"))


def _has_required_section_identity(row: dict[str, Any]) -> bool:
    return (
        _nonempty_string(row.get("id")) is not None
        and _nonempty_string(row.get("section_key")) is not None
        and _positive_integer(row.get("version")) is not None
    )
