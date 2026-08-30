"""Dialect-aware column types.

Postgres 16 is the datastore (CODE-01 §1). SQLite is supported for the local
test path only, so that the migrations and the acceptance test can run on a
machine without Docker. See SUBMISSION.md "Declared deviations".

Every difference between the two dialects is isolated in this file. No other
module branches on the dialect for a column type.
"""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import JSON, Text
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.types import TypeDecorator


class StringArray(TypeDecorator):
    """TEXT[] on Postgres, a JSON array elsewhere.

    Holds actors.groups — the column inbound clearance reads.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(pg.ARRAY(Text()))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Sequence[str] | None, dialect: Any) -> Any:
        if value is None:
            return None
        return list(value)

    def process_result_value(self, value: Any, dialect: Any) -> list[str]:
        if value is None:
            return []
        return list(value)


class JSONB(TypeDecorator):
    """JSONB on Postgres, JSON elsewhere. Holds ledger.payload_json."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(pg.JSONB())
        return dialect.type_descriptor(JSON())
