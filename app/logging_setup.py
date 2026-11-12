"""JSON logs, one object per line, every line carrying the request id of the request that caused it."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import TextIO

from app.request_context import request_id_var

LOGGER_NAME = "classtasks"  # every log line of this app comes from a logger under this name

_STANDARD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime", "request_id"}


class RequestIdFilter(logging.Filter):
    """Stamps the current request id on each record, unless the caller already named one (the 500 handler does)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "request_id", None) is None:
            record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD and not key.startswith("_"):
                data[key] = value  # whatever was passed with extra={...}
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)  # one string: the line stays one line
        return json.dumps(data, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    """Safe to call again: the old handler is replaced, never stacked (stacking prints every line twice)."""
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
