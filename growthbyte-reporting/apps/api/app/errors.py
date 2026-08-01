import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import SafeApplicationError

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(SafeApplicationError)
    async def handle_safe_application_error(
        request: Request, error: SafeApplicationError
    ) -> JSONResponse:
        logger.warning(
            "Application request failed",
            extra={"path": request.url.path, "error_code": error.code},
        )
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "message": error.safe_message}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "Request validation failed",
            extra={"path": request.url.path, "error_code": "validation_error"},
        )
        details = [
            {
                "location": list(item["loc"]),
                "code": item["type"],
                "message": item["msg"],
            }
            for item in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, _error: Exception) -> JSONResponse:
        logger.error("Unhandled application error", extra={"path": request.url.path})
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Unexpected server error"}},
        )
