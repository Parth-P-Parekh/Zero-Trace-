"""structlog JSON logging with a redacting processor. CODE-01 §21.3.

Wired at M0, not retrofitted. The processor exists before there is anything to
redact, because a log line is the easiest place for a secret to escape and the
hardest place to notice it later.

On the `re` import: CODE-01 §1 mandates google-re2 for *detectors*, because A4
writes detector patterns at runtime and a ReDoS in a generated pattern is the
whole story going wrong. These patterns are fixed, authored by us, and never
derived from input, so stdlib `re` is correct here. Nothing in detect/ may do
this.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

REDACTED = "[REDACTED]"

# Key names whose value is never safe to print.
_SECRET_KEYS = re.compile(
    r"(secret|password|passwd|token|api_?key|authorization|auth|cookie|"
    r"session|dsn|credential|private_?key|master_?key)",
    re.IGNORECASE,
)

# Value shapes that are never safe to print, whatever the key is called.
_SECRET_VALUES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("bearer", re.compile(r"Bearer\s+[A-Za-z0-9._\-]{8,}", re.IGNORECASE)),
    ("provider_key", re.compile(r"\b(sk|pk|rk)-[A-Za-z0-9._\-]{12,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}")),
    ("pem", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("db_uri", re.compile(r"\b[a-z0-9+]+://[^\s:@/]+:[^\s:@/]+@[^\s]+", re.IGNORECASE)),
    ("long_digits", re.compile(r"\b\d{12,19}\b")),
    ("high_entropy", re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")),
)

_MAX_DEPTH = 8


def _redact_text(value: str) -> str:
    for _name, pattern in _SECRET_VALUES:
        value = pattern.sub(REDACTED, value)
    return value


def _redact(value: Any, *, key: str | None = None, depth: int = 0) -> Any:
    if depth > _MAX_DEPTH:
        return REDACTED
    if key is not None and _SECRET_KEYS.search(key):
        return REDACTED
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        return {k: _redact(v, key=str(k), depth=depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(v, depth=depth + 1) for v in value]
    if isinstance(value, bytes):
        return REDACTED
    return value


def redacting_processor(
    _logger: Any, _name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Remove secrets from every log event, by key name and by value shape."""
    return {k: _redact(v, key=str(k)) for k, v in event_dict.items()}


def configure(level: str = "info", *, json_output: bool = True) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=numeric)

    renderer = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redacting_processor,  # last thing before rendering
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)
