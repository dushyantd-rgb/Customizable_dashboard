"""FastAPI construction for the SuperK one-click reporting service."""

from typing import Annotated

from fastapi import Depends, Request

from app.api.v1.dependencies import ReportingClientDependency
from app.integrations.google.search_console.repository import SearchConsoleRepository
from app.integrations.google.search_console.service import SearchConsoleService
from app.superk.repository import SuperKRepository
from app.superk.service import SuperKReportingService


def get_superk_service(
    request: Request,
    reporting_client: ReportingClientDependency,
) -> SuperKReportingService:
    settings = request.app.state.settings
    gsc_repository = None
    gsc_service = None
    if settings.token_encryption_key is not None:
        gsc_repository = SearchConsoleRepository(
            reporting_client,
            settings.token_encryption_key,
        )
        gsc_service = SearchConsoleService(
            repository=gsc_repository,
            settings=settings,
        )
    return SuperKReportingService(
        repository=SuperKRepository(reporting_client),
        settings=settings,
        gsc_repository=gsc_repository,
        gsc_service=gsc_service,
    )


SuperKServiceDependency = Annotated[SuperKReportingService, Depends(get_superk_service)]
