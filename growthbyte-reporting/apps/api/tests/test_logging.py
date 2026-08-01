import io
import logging

from app.core.logging import JsonFormatter, configure_logging


def test_http_client_request_metadata_is_not_emitted_at_debug_level() -> None:
    root_logger = logging.getLogger()
    httpx_logger = logging.getLogger("httpx")
    httpcore_logger = logging.getLogger("httpcore")
    original_root_handlers = tuple(root_logger.handlers)
    original_root_level = root_logger.level
    original_httpx_level = httpx_logger.level
    original_httpcore_level = httpcore_logger.level
    output = io.StringIO()

    try:
        configure_logging("DEBUG")
        handler = logging.StreamHandler(output)
        handler.setFormatter(JsonFormatter())
        root_logger.handlers = [handler]

        sensitive_fragment = (
            "https://synthetic-project.supabase.co/rest/v1/client_knowledge"
            "?client_id=eq.00000000-0000-4000-8000-0000000000aa"
            " apikey=synthetic-service-role-key"
        )
        httpx_logger.info("HTTP Request: GET %s", sensitive_fragment)
        httpcore_logger.debug("request headers %s", sensitive_fragment)
        httpx_logger.warning("HTTP request failed: %s", sensitive_fragment)

        rendered = output.getvalue()
        assert "HTTP request failed: %s" in rendered
        assert "synthetic-project" not in rendered
        assert "synthetic-service-role-key" not in rendered
        assert "00000000-0000-4000-8000-0000000000aa" not in rendered
        assert httpx_logger.getEffectiveLevel() >= logging.WARNING
        assert httpcore_logger.getEffectiveLevel() >= logging.WARNING
    finally:
        root_logger.handlers = list(original_root_handlers)
        root_logger.setLevel(original_root_level)
        httpx_logger.setLevel(original_httpx_level)
        httpcore_logger.setLevel(original_httpcore_level)
