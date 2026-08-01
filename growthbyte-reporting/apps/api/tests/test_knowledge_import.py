from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.knowledge.errors import (
    ApplyConfirmationError,
    InvalidClientIdError,
    MissingKnowledgeFieldsError,
    MissingTargetClientError,
)
from app.knowledge.service import KnowledgeImportService
from app.knowledge.source import ReadOnlyKnowledgeAdapter
from app.repositories.client_knowledge import ClientKnowledgeRepository
from app.repositories.clients import ReportingClientRepository
from tests.helpers import FakeKnowledgeClient, FakeReportingClient, source_rows

TARGET_CLIENT_ID = "00000000-0000-4000-8000-000000000010"


def _service(reporting: FakeReportingClient, source: FakeKnowledgeClient) -> KnowledgeImportService:
    return KnowledgeImportService(
        clients=ReportingClientRepository(reporting),
        knowledge=ClientKnowledgeRepository(reporting),
        source=ReadOnlyKnowledgeAdapter(source),
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        batch_id_factory=lambda: UUID("00000000-0000-4000-8000-000000000030"),
    )


@pytest.mark.asyncio
async def test_preview_performs_zero_writes_and_returns_no_source_payload() -> None:
    reporting = FakeReportingClient()
    source = FakeKnowledgeClient(rows=source_rows())

    preview = await _service(reporting, source).preview(
        source_client_identifier="source-client",
        target_client_id=TARGET_CLIENT_ID,
        target_status="draft",
    )
    serialized = preview.model_dump_json()

    assert preview.writes_performed == 0
    assert preview.mapped_record_count == 1
    assert reporting.upsert_calls == []
    assert "synthetic fragment" not in serialized
    assert "00000000-0000-4000-8000-000000000020" not in serialized


@pytest.mark.asyncio
async def test_missing_target_and_invalid_target_are_safe_and_stop_source_reads() -> None:
    missing_reporting = FakeReportingClient(client_exists=False)
    missing_source = FakeKnowledgeClient(rows=source_rows())
    with pytest.raises(MissingTargetClientError):
        await _service(missing_reporting, missing_source).preview(
            source_client_identifier="source-client",
            target_client_id=TARGET_CLIENT_ID,
        )
    assert missing_source.select_calls == []

    with pytest.raises(InvalidClientIdError):
        await _service(FakeReportingClient(), FakeKnowledgeClient()).preview(
            source_client_identifier="source-client",
            target_client_id="invalid",
        )


@pytest.mark.asyncio
async def test_repeated_apply_is_idempotent_and_never_deletes() -> None:
    reporting = FakeReportingClient()
    service = _service(reporting, FakeKnowledgeClient(rows=source_rows()))

    first = await service.apply(
        source_client_identifier="source-client",
        target_client_id=TARGET_CLIENT_ID,
        confirm_target_client_id=TARGET_CLIENT_ID,
        target_status="draft",
    )
    second = await service.apply(
        source_client_identifier="source-client",
        target_client_id=TARGET_CLIENT_ID,
        confirm_target_client_id=TARGET_CLIENT_ID,
        target_status="draft",
    )

    assert first.upserted_record_count == second.upserted_record_count == 1
    assert len(reporting.rows_by_source_identity) == 1
    assert len(reporting.upsert_calls) == 2
    assert first.deleted_record_count == second.deleted_record_count == 0
    assert not hasattr(reporting, "delete")


@pytest.mark.asyncio
async def test_apply_requires_matching_confirmation_and_complete_fields() -> None:
    service = _service(FakeReportingClient(), FakeKnowledgeClient(rows=source_rows()))
    with pytest.raises(ApplyConfirmationError):
        await service.apply(
            source_client_identifier="source-client",
            target_client_id=TARGET_CLIENT_ID,
            confirm_target_client_id="00000000-0000-4000-8000-000000000011",
            target_status="draft",
        )

    incomplete = _service(
        FakeReportingClient(),
        FakeKnowledgeClient(rows=source_rows(section_overrides={"version": None})),
    )
    with pytest.raises(MissingKnowledgeFieldsError):
        await incomplete.apply(
            source_client_identifier="source-client",
            target_client_id=TARGET_CLIENT_ID,
            confirm_target_client_id=TARGET_CLIENT_ID,
            target_status="draft",
        )
