"""Dependencies for Google Sheets integration endpoints."""

from typing import Annotated, cast

from fastapi import Depends, Request

from app.core.config import get_settings
from app.data.supabase import ReportingSupabaseClientProtocol
from app.integrations.google.repository import GoogleSheetsRepository
from app.integrations.google.service import GoogleSheetsService
from app.knowledge.errors import PlaceholderCredentialsError


def get_google_repository(request: Request) -> GoogleSheetsRepository:
    """Get a Google Sheets repository from app state.

    Args:
        request: FastAPI request object.

    Returns:
        GoogleSheetsRepository instance.

    Raises:
        PlaceholderCredentialsError: If Supabase not configured.
    """
    settings = get_settings()

    if (
        not settings.token_encryption_key
        or not settings.token_encryption_key.get_secret_value()
    ):
        raise PlaceholderCredentialsError

    client = request.app.state.reporting_supabase_client
    if client is None:
        raise PlaceholderCredentialsError

    return GoogleSheetsRepository(
        client=cast(ReportingSupabaseClientProtocol, client),
        encryption_key=settings.token_encryption_key,
    )


def get_google_service(
    repository: Annotated[
        GoogleSheetsRepository,
        Depends(get_google_repository),
    ],
) -> GoogleSheetsService:
    """Get a Google Sheets service.

    Args:
        repository: Google Sheets repository.

    Returns:
        GoogleSheetsService instance.
    """
    settings = get_settings()
    return GoogleSheetsService(
        repository=repository,
        settings=settings,
    )


# Type aliases for dependency injection
GoogleRepositoryDependency = Annotated[
    GoogleSheetsRepository,
    Depends(get_google_repository),
]
GoogleServiceDependency = Annotated[
    GoogleSheetsService,
    Depends(get_google_service),
]
