"""FastAPI dependencies for Meta Ads."""

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request

from app.data.supabase import ReportingSupabaseClientProtocol
from app.integrations.meta.client import MetaGraphClient
from app.integrations.meta.repository import MetaRepository
from app.integrations.meta.service import MetaSyncService
from app.knowledge.errors import PlaceholderCredentialsError


async def get_meta_client(request: Request) -> AsyncIterator[MetaGraphClient]:
    settings = request.app.state.settings
    if settings.meta.access_token is None:
        raise PlaceholderCredentialsError
    client = MetaGraphClient(
        access_token=settings.meta.access_token.get_secret_value(),
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
