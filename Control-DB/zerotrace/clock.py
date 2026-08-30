"""The one clock. CODE-01 §1: one now() helper, UTC, injectable.

No other module calls datetime.now(). The ledger's hashes must be reproducible,
so the time source has to be replaceable in a test.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable, Iterator

_source: Callable[[], datetime] = lambda: datetime.now(timezone.utc)


def now() -> datetime:
    """Current time, always timezone-aware UTC."""
    return _source()


def set_source(fn: Callable[[], datetime]) -> None:
    global _source
    _source = fn


def reset() -> None:
    global _source
    _source = lambda: datetime.now(timezone.utc)


@contextmanager
def frozen(at: datetime) -> Iterator[datetime]:
    """Freeze the clock for a block. Used by ledger determinism tests."""
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    previous = _source
    set_source(lambda: at)
    try:
        yield at
    finally:
        globals()["_source"] = previous


def as_utc(ts: datetime) -> datetime:
    """Normalise any datetime to aware UTC.

    SQLite gives back naive datetimes. The ledger canonicalises through this so a
    hash computed on write matches the hash recomputed on verify, on any dialect.
    """
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def iso(ts: datetime) -> str:
    """The single timestamp spelling used inside ledger records."""
    return as_utc(ts).isoformat(timespec="microseconds")
