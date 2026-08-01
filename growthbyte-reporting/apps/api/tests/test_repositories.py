from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.knowledge.models import MappedKnowledgeRecord
from app.repositories.client_knowledge import (
    SOURCE_IDENTITY_CONFLICT_TARGET,
    ClientKnowledgeRepository,
)
from app.repositories.clients import ReportingClientRepository
from tests.helpers import FakeReportingClient

TARGET_CLIENT_ID = UUID("00000000-0000-4000-8000-000000000010")


@pytest.mark.asyncio
async def test_client_repository_requires_explicit_client_filter() -> None:
    client = FakeReportingClient()
    repository = ReportingClientRepository(client)

    assert await repository.exists(client_id=TARGET_CLIENT_ID) is True
    assert client.select_calls == [
        {
            "table": "clients",
            "columns": ("id",),
            "filters": {"id": str(TARGET_CLIENT_ID)},
            "limit": 1,
        }
    ]
    with pytest.raises(TypeError):
        await repository.exists()  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_knowledge_upsert_preserves_client_scope_and_uses_atomic_conflict_target() -> None:
    client = FakeReportingClient()
    repository = ClientKnowledgeRepository(client)
    record = MappedKnowledgeRecord(
        category="sample",
        knowledge_key="sample",
        value={"content": "synthetic fragment"},
        status="draft",
        source_type="knowledge_supabase_section",
        source_identifier="source-row",
        source_display_name=None,
        source_reference="org_knowledge_base_sections",
        source_version="2",
        source_hash="0" * 64,
        version=2,
    )

    count = await repository.upsert_imported(
        client_id=TARGET_CLIENT_ID,
        records=(record,),
        imported_at=datetime(2026, 1, 1, tzinfo=UTC),
        import_batch_id=UUID("00000000-0000-4000-8000-000000000030"),
    )

    assert count == 1
    assert client.upsert_calls[0]["on_conflict"] == SOURCE_IDENTITY_CONFLICT_TARGET
    assert client.upsert_calls[0]["rows"][0]["client_id"] == str(TARGET_CLIENT_ID)
    assert not hasattr(repository, "delete")
    assert not hasattr(client, "delete")
