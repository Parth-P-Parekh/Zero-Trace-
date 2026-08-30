#!/usr/bin/env python3
"""Run the transport-independent harness checks without starting a provider API."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.conformance import load_fixtures, structural_failures  # noqa: E402


def main() -> int:
    failed = False
    fixtures = load_fixtures(ROOT / "gateway" / "conformance")
    for fixture in fixtures:
        failures = structural_failures(fixture)
        if failures:
            failed = True
            print(f"FAIL {fixture.name}: {'; '.join(failures)}")
        else:
            print(f"PASS {fixture.name}")
    print(f"{len(fixtures)} harness fixture(s) checked")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
