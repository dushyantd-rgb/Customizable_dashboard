"""FastAPI dependencies for Meta Ads."""

from collections.abc import AsyncIterator
from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Request

from app.api.v1.dependencies import ReportingClientDependency
from app.core.errors import ClientNotFoundError, ConnectorConfigurationError
from app.data.supabase import ReportingSupabaseClientProtocol
from app.integrations.meta.client import MetaGraphClient
from app.integrations.meta.repository import MetaRepository
from app.integrations.meta.service import MetaSyncService
from app.knowledge.errors import PlaceholderCredentialsError
from app.repositories.clients import ReportingClientRepository


async def get_meta_client(
    client_id: UUID,
    request: Request,
    reporting_client: ReportingClientDependency,
) -> AsyncIterator[MetaGraphClient]:
    settings = request.app.state.settings
    client_record = await ReportingClientRepository(reporting_client).get(client_id=client_id)
    if client_record is None:
        raise ClientNotFoundError
    access_token = settings.meta.access_token_for_client(client_record.slug)
    if access_token is None:
        raise ConnectorConfigurationError
    client = MetaGraphClient(
        access_token=access_token.get_secret_value(),
        api_version=settings.meta.graph_api_version,
    )
    try:
        yield client
    finally:
        await client.close()


def get_meta_repository(request: Request) -> MetaRepository:
    client = request.app.state.reporting_supabase_client
    if client is None:
        raise PlaceholderCredentialsError
    return MetaRepository(cast(ReportingSupabaseClientProtocol, client))


def get_meta_sync_service(
    meta_client: Annotated[MetaGraphClient, Depends(get_meta_client)],
    repository: Annotated[MetaRepository, Depends(get_meta_repository)],
) -> MetaSyncService:
    return MetaSyncService(meta_client=meta_client, repository=repository)


MetaClientDependency = Annotated[MetaGraphClient, Depends(get_meta_client)]
MetaRepositoryDependency = Annotated[MetaRepository, Depends(get_meta_repository)]
MetaSyncServiceDependency = Annotated[MetaSyncService, Depends(get_meta_sync_service)]
