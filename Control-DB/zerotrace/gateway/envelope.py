"""The one error envelope for every gateway and control failure.

    {"error": {"code": "<stable code>", "message": "<safe message>"},
     "request_id": "<id>", "ledger_id": <int|null>}

Clients match on `code` (a stable zt.* wire code), never on prose. The
request_id comes from the request-context middleware; the ledger_id is the
evidence record that decided or failed the request, when one exists.
"""

from __future__ import annotations

from typing import Any

import structlog


def error_envelope(
    code: str, message: str, *, ledger_id: int | None = None
) -> dict[str, Any]:
    request_id = structlog.contextvars.get_contextvars().get("request_id")
    return {
        "error": {"code": code, "message": message},
        "request_id": request_id or "",
        "ledger_id": ledger_id,
    }
