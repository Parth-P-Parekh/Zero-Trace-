#!/usr/bin/env python3
"""Run a harness script against *this* checkout.

The harness was written on the auditor's machine and every script begins with
`sys.path.insert(0, '/root/zt')`. Those paths do not exist here, which is harmless -- a
`sys.path` entry that resolves to nothing is simply never matched -- but it means the
imports only work if the repo root and the harness directory are already on the path.

Rather than editing twenty-four files and thereby changing the artefact an independent
tester delivered, this puts the right directories on `sys.path` and runs the script
unmodified. What the judges see is the auditor's code, not our edit of it.

    python zerotrace-test-harness/run.py rag_e2e
    python zerotrace-test-harness/run.py evade fp

Each script runs in a fresh subprocess, because several of them set `ZT_HOME` and seed a
store and would otherwise contaminate each other.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
ROOT = HARNESS.parent


def env_for_harness() -> dict:
    """The repo, the harness and its `rag` package, ahead of anything else."""
    parts = [str(ROOT), str(HARNESS), str(HARNESS / "rag")]
    existing = os.environ.get("PYTHONPATH", "")
    if existing:
        parts.append(existing)
    return {**os.environ, "PYTHONPATH": os.pathsep.join(parts)}


def run(name: str) -> int:
    script = HARNESS / (name if name.endswith(".py") else f"{name}.py")
    if not script.is_file():
        print(f"no such harness script: {script.name}", file=sys.stderr)
        return 2
    print(f"\n{'=' * 72}\n  {script.name}\n{'=' * 72}")
    return subprocess.run([sys.executable, str(script)], cwd=ROOT,
                          env=env_for_harness()).returncode


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        print("available:")
        for path in sorted(HARNESS.glob("*.py")):
            if path.name not in ("run.py", "lib.py"):
                print(f"  {path.stem}")
        return 0
    worst = 0
    for name in argv:
        worst = max(worst, run(name))
    return worst


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
