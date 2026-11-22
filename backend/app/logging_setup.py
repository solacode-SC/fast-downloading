"""Structured JSON logging with automatic redaction of tokens, cookies, and proxy credentials."""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_SENSITIVE_PATTERNS = [
    # Proxy / URL embedded credentials: scheme://user:pass@host
    (re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^:@/\s]+):([^@/\s]+)@"), r"\1***:***@"),
    # Query parameters containing secrets/tokens/signatures/cookies
    (
        re.compile(
            r"([?&](?:token|sig|signature|key|cookie|auth|access_token|sessionid|password|secret)=)[^&\s]+",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]",
    ),
    # Bearer / Cookie headers
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE), r"\1[REDACTED]"),
]


def redact_sensitive(text: str) -> str:
    result = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_ctx.get(),
            "msg": redact_sensitive(record.getMessage()),
        }
        for key in (
            "platform",
            "job_id",
            "error_code",
            "proxy",
            "duration_ms",
            "status_code",
            "method",
            "path",
            "client_ip",
            "bytes_served",
        ):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = redact_sensitive(str(val)) if isinstance(val, str) else val

        if record.exc_info and record.exc_info[0] is not None:
            payload["exc"] = redact_sensitive(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    # Reduce noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
