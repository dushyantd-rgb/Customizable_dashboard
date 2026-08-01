from app.knowledge.mapper import KnowledgeMapper
from app.knowledge.models import MappingDisposition, SourceKnowledgeRecord
from tests.helpers import source_rows


def _records(rows: dict[str, list[dict]]) -> tuple[SourceKnowledgeRecord, ...]:
    return tuple(
        SourceKnowledgeRecord(table=table, fields=row)
        for table, table_rows in rows.items()
        if table != "org_clients"
        for row in table_rows
    )


def test_mapping_classifies_mapped_ignored_and_unresolved_fields() -> None:
    rows = source_rows()
    rows["org_knowledge_items"] = [
        {"id": "synthetic-item", "client_id": "source-client", "content": "fragment"}
    ]
    result = KnowledgeMapper().map(source_records=_records(rows), target_status="draft")

    assert len(result.records) == 1
    assert result.ignored_record_count == 1
    assert result.unresolved_record_count == 0
    assert result.records[0].source_version == "2"
    assert result.records[0].source_hash
    assert {item.disposition for item in result.field_classification} == {
        MappingDisposition.MAPPED,
        MappingDisposition.IGNORED,
        MappingDisposition.UNRESOLVED,
    }
    assert "knowledge_items_excluded_pending_contract_approval" in result.warnings


def test_mapping_reports_missing_fields_and_requires_explicit_status() -> None:
    rows = source_rows(section_overrides={"version": None, "content": None})
    result = KnowledgeMapper().map(source_records=_records(rows), target_status=None)

    assert result.records == ()
    assert result.unresolved_record_count == 1
    assert "target_status_required" in result.blockers
    assert "missing_required_section_fields" in result.blockers
