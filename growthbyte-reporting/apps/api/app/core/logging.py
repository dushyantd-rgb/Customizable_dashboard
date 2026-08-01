import json
import logging
from datetime import UTC, datetime
from typing import Any

_REDACTED_HTTP_LOGGERS = ("httpcore", "httpx")


class JsonFormatter(logging.Formatter):
    """Small allowlist-based JSON formatter that never serializes record arguments."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.msg if isinstance(record.msg, str) else "Application log event"
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }
        return json.dumps(payload, separators=(",", ":"))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level.upper(), handlers=[handler], force=True)
    for logger_name in _REDACTED_HTTP_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
