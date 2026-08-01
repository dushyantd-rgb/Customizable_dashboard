"""FastAPI dependencies for the Google Sheets connector."""

from typing import Annotated, cast

from fastapi import Depends, Request

from app.data.supabase import ReportingSupabaseClientProtocol
from app.integrations.google.repository import GoogleSheetsRepository
from app.integrations.google.service import GoogleSheetsService
from app.knowledge.errors import PlaceholderCredentialsError


def get_google_repository(request: Request) -> GoogleSheetsRepository:
    settings = request.app.state.settings
    client = request.app.state.reporting_supabase_client
    if settings.token_encryption_key is None or client is None:
        raise PlaceholderCredentialsError
    return GoogleSheetsRepository(
        cast(ReportingSupabaseClientProtocol, client),
        settings.token_encryption_key,
    )


def get_google_service(
    request: Request,
    repository: Annotated[GoogleSheetsRepository, Depends(get_google_repository)],
) -> GoogleSheetsService:
    return GoogleSheetsService(repository=repository, settings=request.app.state.settings)


GoogleRepositoryDependency = Annotated[
    GoogleSheetsRepository,
    Depends(get_google_repository),
]
GoogleServiceDependency = Annotated[
    GoogleSheetsService,
    Depends(get_google_service),
]
