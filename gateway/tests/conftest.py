"""Shared test configuration.

The checker enforces a 50ms wall-clock ceiling and degrades when it trips (SKEL-01
§D.3). That is correct in production and a source of flakiness in tests: on a loaded
machine a logic test can exceed the ceiling, get a degraded result, and fail with an
assertion about headers rather than about the thing it was testing. It reproduces
exactly by forcing a low ceiling.

So logic tests run with the ceiling effectively disabled. Timing behaviour is not
untested -- it is tested deliberately, by the tests that construct their own
``CheckerConfig`` with a specific ceiling, which is the only place a wall-clock
assertion belongs.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _generous_checker_ceiling(monkeypatch):
    monkeypatch.setenv("ZT_CHECKER_CEILING_MS", "10000")
