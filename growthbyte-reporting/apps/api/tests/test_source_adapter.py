import pytest

from app.knowledge.errors import (
    DuplicateSourceClientError,
    InvalidSourceClientIdentifierError,
    MissingSourceClientError,
)
from app.knowledge.source import ReadOnlyKnowledgeAdapter
from tests.helpers import FakeKnowledgeClient, source_rows


@pytest.mark.asyncio
async def test_source_adapter_exposes_reads_only_and_filters_every_related_table() -> None:
    client = FakeKnowledgeClient(rows=source_rows())
    adapter = ReadOnlyKnowledgeAdapter(client)

    source_client = await adapter.get_client(source_client_identifier="source-client")
    records = await adapter.list_knowledge(source_client_identifier=source_client.identifier)

    assert len(records) == 1
    assert {call["table"] for call in client.select_calls} == {
        "org_clients",
        "org_knowledge_items",
        "org_knowledge_base_sections",
    }
    assert all(call["filters"] for call in client.select_calls)
    for mutation_name in ("insert", "update", "upsert", "delete", "rpc"):
        assert not hasattr(adapter, mutation_name)
        assert not hasattr(client, mutation_name)


@pytest.mark.asyncio
async def test_source_adapter_handles_missing_duplicate_and_invalid_clients() -> None:
    missing = ReadOnlyKnowledgeAdapter(FakeKnowledgeClient())
    duplicate = ReadOnlyKnowledgeAdapter(
        FakeKnowledgeClient(rows={"org_clients": [{"id": "same"}, {"id": "same"}]})
    )

    with pytest.raises(MissingSourceClientError):
        await missing.get_client(source_client_identifier="missing")
    with pytest.raises(DuplicateSourceClientError):
        await duplicate.get_client(source_client_identifier="same")
    with pytest.raises(InvalidSourceClientIdentifierError):
        await missing.get_client(source_client_identifier=" ")
