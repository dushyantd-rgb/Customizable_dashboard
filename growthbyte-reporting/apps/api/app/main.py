import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.router import router as v1_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.data.supabase import (
    SupabaseReadClient,
    create_knowledge_supabase_client,
    create_reporting_supabase_client,
)
from app.errors import register_error_handlers

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


def _lifespan() -> object:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        owned_clients: list[SupabaseReadClient] = []
        application_settings: Settings = application.state.settings

        logger.info(f"Checking Supabase config: reporting={application_settings.reporting_supabase.configured}, knowledge={application_settings.knowledge_supabase.configured}")

        if (
            application.state.reporting_supabase_client is None
            and application_settings.reporting_supabase.configured
        ):
            try:
                client = create_reporting_supabase_client(application_settings.reporting_supabase)
                application.state.reporting_supabase_client = client
                owned_clients.append(client)
                logger.info("Reporting Supabase client created successfully")
            except Exception as e:
                logger.error(f"Failed to create reporting Supabase client: {e}")

        if (
            application.state.knowledge_supabase_client is None
            and application_settings.knowledge_supabase.configured
        ):
            try:
                client = create_knowledge_supabase_client(application_settings.knowledge_supabase)
                application.state.knowledge_supabase_client = client
                owned_clients.append(client)
                logger.info("Knowledge Supabase client created successfully")
            except Exception as e:
                logger.error(f"Failed to create knowledge Supabase client: {e}")

        logger.info("API service starting")
        try:
            yield
        finally:
            for owned_client in owned_clients:
                await owned_client.close()
            logger.info("API service stopping")

    return lifespan


def create_app(
    *,
    application_settings: Settings | None = None,
    reporting_supabase_client: SupabaseReadClient | None = None,
    knowledge_supabase_client: SupabaseReadClient | None = None,
) -> FastAPI:
    resolved_settings = application_settings or settings
    application = FastAPI(
        title="GrowthByte Reporting API",
        version=resolved_settings.app_version,
        lifespan=_lifespan(),
    )
    application.state.settings = resolved_settings
    application.state.reporting_supabase_client = reporting_supabase_client
    application.state.knowledge_supabase_client = knowledge_supabase_client
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[resolved_settings.web_url.rstrip("/")],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    application.include_router(health_router)
    application.include_router(v1_router)
    register_error_handlers(application)
    return application


app = create_app()
