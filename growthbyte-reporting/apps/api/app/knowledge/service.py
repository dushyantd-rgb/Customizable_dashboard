from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.knowledge.errors import (
    ApplyConfirmationError,
    InvalidClientIdError,
    MappingValidationError,
    MissingKnowledgeFieldsError,
    MissingTargetClientError,
)
from app.knowledge.mapper import KnowledgeMapper
from app.knowledge.models import (
    KnowledgeImportPreview,
    KnowledgeImportResult,
    MappingResult,
)
from app.knowledge.source import ReadOnlyKnowledgeAdapter
from app.repositories.client_knowledge import ClientKnowledgeRepository
from app.repositories.clients import ReportingClientRepository


@dataclass(frozen=True)
class _ImportPlan:
    target_client_id: UUID
    mapping: MappingResult


class KnowledgeImportService:
    def __init__(
        self,
        *,
        clients: ReportingClientRepository,
        knowledge: ClientKnowledgeRepository,
        source: ReadOnlyKnowledgeAdapter,
        mapper: KnowledgeMapper | None = None,
        clock: Callable[[], datetime] | None = None,
        batch_id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        self.__clients = clients
        self.__knowledge = knowledge
        self.__source = source
        self.__mapper = mapper or KnowledgeMapper()
        self.__clock = clock or (lambda: datetime.now(UTC))
        self.__batch_id_factory = batch_id_factory or uuid4

    async def preview(
        self,
        *,
        source_client_identifier: str,
        target_client_id: str,
        target_status: str | None = None,
    ) -> KnowledgeImportPreview:
        plan = await self.__build_plan(
            source_client_identifier=source_client_identifier,
            target_client_id=target_client_id,
            target_status=target_status,
        )
        return _preview_from_mapping(plan.mapping)

    async def apply(
        self,
        *,
        source_client_identifier: str,
        target_client_id: str,
        confirm_target_client_id: str,
        target_status: str,
    ) -> KnowledgeImportResult:
        parsed_target_id = _parse_client_id(target_client_id)
        if _parse_client_id(confirm_target_client_id) != parsed_target_id:
            raise ApplyConfirmationError

        plan = await self.__build_plan(
            source_client_identifier=source_client_identifier,
            target_client_id=target_client_id,
            target_status=target_status,
        )
        if plan.mapping.blockers:
            if "missing_required_section_fields" in plan.mapping.blockers:
                raise MissingKnowledgeFieldsError
            raise MappingValidationError

        imported_count = await self.__knowledge.upsert_imported(
            client_id=plan.target_client_id,
            records=plan.mapping.records,
            imported_at=self.__clock(),
            import_batch_id=self.__batch_id_factory(),
        )
        return KnowledgeImportResult(
            source_record_count=plan.mapping.source_record_count,
            upserted_record_count=imported_count,
        )

    async def __build_plan(
        self,
        *,
        source_client_identifier: str,
        target_client_id: str,
        target_status: str | None,
    ) -> _ImportPlan:
        parsed_target_id = _parse_client_id(target_client_id)
        if not await self.__clients.exists(client_id=parsed_target_id):
            raise MissingTargetClientError
        source_client = await self.__source.get_client(
            source_client_identifier=source_client_identifier
        )
        source_records = await self.__source.list_knowledge(
            source_client_identifier=source_client.identifier
        )
        mapping = self.__mapper.map(
            source_records=source_records,
            target_status=target_status,
        )
        return _ImportPlan(target_client_id=parsed_target_id, mapping=mapping)


def _parse_client_id(value: str) -> UUID:
    try:
        return UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise InvalidClientIdError from error


def _preview_from_mapping(mapping: MappingResult) -> KnowledgeImportPreview:
    return KnowledgeImportPreview(
        source_record_count=mapping.source_record_count,
        mapped_record_count=len(mapping.records),
        ignored_record_count=mapping.ignored_record_count,
        unresolved_record_count=mapping.unresolved_record_count,
        field_classification=mapping.field_classification,
        warnings=mapping.warnings,
        blockers=mapping.blockers,
    )
