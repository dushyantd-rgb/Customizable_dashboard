import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.knowledge.errors import (
    DuplicateSourceClientError,
    KnowledgeImportError,
    MissingSourceClientError,
    MissingTargetClientError,
    ReportingDatabaseUnavailableError,
    SourceDatabaseUnavailableError,
    UpsertConflictError,
)

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(KnowledgeImportError)
    async def handle_knowledge_import_error(
        request: Request, error: KnowledgeImportError
    ) -> JSONResponse:
        logger.warning(
            "Knowledge import request failed",
            extra={"path": request.url.path, "error_code": error.code},
        )
        status_code = 400
        if isinstance(error, MissingSourceClientError | MissingTargetClientError):
            status_code = 404
        elif isinstance(error, DuplicateSourceClientError | UpsertConflictError):
            status_code = 409
        elif isinstance(
            error,
            ReportingDatabaseUnavailableError | SourceDatabaseUnavailableError,
        ):
            status_code = 503
        return JSONResponse(
            status_code=status_code,
            content={"error": {"code": error.code, "message": error.safe_message}},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, _error: Exception) -> JSONResponse:
        logger.error("Unhandled application error", extra={"path": request.url.path})
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Unexpected server error"}},
        )
