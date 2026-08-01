"""Dependencies for Meta integration endpoints."""

from typing import Annotated, cast

from fastapi import Depends, Request

from app.core.config import get_settings
from app.data.supabase import ReportingSupabaseClientProtocol
from app.integrations.meta.client import MetaGraphClient
from app.integrations.meta.repository import MetaRepository
from app.integrations.meta.service import MetaSyncService
from app.knowledge.errors import PlaceholderCredentialsError


def get_meta_client(request: Request) -> MetaGraphClient:
    """Get a Meta Graph API client from app state."""
    settings = get_settings()

    if (
        not settings.meta.access_token
        or not settings.meta.access_token.get_secret_value()
    ):
        raise PlaceholderCredentialsError

    # Create a new client for each request (they're cheap to create)
    return MetaGraphClient(
        access_token=settings.meta.access_token.get_secret_value(),
        api_version=settings.meta.graph_api_version,
    )


def get_meta_repository(request: Request) -> MetaRepository:
    """Get a Meta repository from app state."""
    client = request.app.state.reporting_supabase_client
    if client is None:
        raise PlaceholderCredentialsError
    return MetaRepository(cast(ReportingSupabaseClientProtocol, client))


def get_meta_sync_service(
    meta_client: Annotated[MetaGraphClient, Depends(get_meta_client)],
    repository: Annotated[MetaRepository, Depends(get_meta_repository)],
) -> MetaSyncService:
    """Get a Meta sync service."""
    return MetaSyncService(meta_client=meta_client, repository=repository)


MetaClientDependency = Annotated[MetaGraphClient, Depends(get_meta_client)]
MetaRepositoryDependency = Annotated[MetaRepository, Depends(get_meta_repository)]
MetaSyncServiceDependency = Annotated[
    MetaSyncService, Depends(get_meta_sync_service)
]
