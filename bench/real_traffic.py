"""Run the checker over real Claude Code turns and report what it does.

Synthetic corpora tell you a detector matches what you thought to write down. They tell
you nothing about the false-positive rate, because you do not think to write down the
things that trip it -- a go.sum line, a base64 favicon, a UUID in a log. So this reads
actual transcripts off this machine and measures against them.

**Nothing sensitive is printed.** Findings are reported as class, span path and a
character-class shape (``sk-ant-...`` becomes ``aa-aaa-...``); values never leave this
process. That is the same rule the escalation queue follows (CODE-01 §10.2), and it
applies here for the same reason: these are the operator's real files.

    python bench/real_traffic.py            # ~60 turns, sampled across projects
    python bench/real_traffic.py --turns 200
    python bench/real_traffic.py --show-shapes
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gateway.base.cache import NullSpanCache                       # noqa: E402
from gateway.base.checker import Checker, CheckerConfig            # noqa: E402
from gateway.base.scanner import DetectorPack                      # noqa: E402
from gateway.check import text_tree, to_verdict                    # noqa: E402
from gateway.detect.encodings import EncodedScanner                # noqa: E402
from gateway.detect.obfuscation import ObfuscationScanner          # noqa: E402
from gateway.detect.s0_credentials import scan_span_credentials    # noqa: E402
from gateway.detect.s1_context import ContextScanner               # noqa: E402
from gateway.detectors.example import EXAMPLE_DETECTORS            # noqa: E402
from gateway.intel.features import shape_of                        # noqa: E402


def transcripts() -> list[Path]:
    root = Path.home() / ".claude" / "projects"
    return sorted(root.rglob("*.jsonl"))


def turns(paths: list[Path], want: int, seed: int = 7) -> list[dict]:
    """Sample user turns across projects.

    Sampled rather than taken head-first: the opening turns of a session are
    unrepresentative (they are setup), and one chatty project would otherwise dominate.
    """
    rng = random.Random(seed)
    by_project: dict[str, list[dict]] = {}

    for p in paths:
        project = p.parts[-2] if p.parts[-2] != "projects" else p.stem
        try:
            with p.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        o = json.loads(line)
                    except ValueError:
                        continue
                    if o.get("type") != "user":
                        continue
                    text = _user_text(o)
                    if text and len(text.strip()) > 3:
                        by_project.setdefault(project, []).append(
                            {"project": project, "text": text}
                        )
        except OSError:
            continue

    if not by_project:
        return []

    # Round-robin across projects so the sample is not one session's voice.
    pools = [rng.sample(v, len(v)) for v in by_project.values()]
    out: list[dict] = []
    i = 0
    while len(out) < want and any(pools):
        pool = pools[i % len(pools)]
        if pool:
            out.append(pool.pop())
        i += 1
        if i > want * 20:
            break
    return out[:want]


def _user_text(rec: dict) -> str:
    msg = rec.get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif block.get("type") == "tool_result":
                c = block.get("content")
                if isinstance(c, str):
                    parts.append(c)
                elif isinstance(c, list):
                    parts.extend(
                        b.get("text", "") for b in c if isinstance(b, dict)
                    )
        return "\n".join(p for p in parts if p)
    return ""


def build_checker() -> Checker:
    detectors = list(EXAMPLE_DETECTORS)
    pack = DetectorPack.build(
        detectors,
        version=1,
        scanners=[
            scan_span_credentials,
            ObfuscationScanner(detectors),
            ContextScanner(),
            EncodedScanner(scan_span_credentials),
        ],
    )
    # NullSpanCache so every turn is measured cold. A warm cache would flatter the
    # numbers and hide the cost that actually matters -- the first time a span is seen.
    return Checker(pack, NullSpanCache(), b"bench-key",
                   CheckerConfig(ceiling_ms=10_000))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, default=60)
    ap.add_argument("--show-shapes", action="store_true",
                    help="print char-class skeletons of hits (never the values)")
    args = ap.parse_args()

    paths = transcripts()
    sample = turns(paths, args.turns)
    if not sample:
        sys.exit("no transcripts found under ~/.claude/projects")

    checker = build_checker()
    lat: list[float] = []
    classes: Counter = Counter()
    per_project: Counter = Counter()
    flagged: list[dict] = []
    sizes: list[int] = []

    for t in sample:
        text = t["text"]
        sizes.append(len(text))
        started = time.perf_counter()
        result = asyncio.run(checker.check(text_tree(text), "bench"))
        lat.append((time.perf_counter() - started) * 1000)

        verdict = to_verdict(result)
        for f in result.findings:
            classes[f.entity_class.value] += 1
        if not verdict.allow:
            per_project[t["project"]] += 1
            hits = [f for f in result.findings if not f.advisory_only]
            flagged.append({
                "project": t["project"],
                "chars": len(text),
                "classes": sorted({f.entity_class.value for f in hits}),
                "detectors": sorted({f.detector_name for f in hits}),
                # Shape only. The value never leaves this process.
                "shapes": [shape_of(text[f.start:f.end], cap=28) for f in hits[:3]],
            })

    n = len(sample)
    print(f"\n{'=' * 66}")
    print(f"  REAL CLAUDE CODE TRAFFIC  --  {n} turns, {len(paths)} transcripts")
    print(f"{'=' * 66}\n")

    print(f"  turns scanned      {n}")
    print(f"  projects           {len({t['project'] for t in sample})}")
    print(f"  total content      {sum(sizes):,} chars")
    print(f"  median turn        {int(statistics.median(sizes)):,} chars")
    print(f"  largest turn       {max(sizes):,} chars\n")

    print(f"  BLOCKED            {len(flagged)} / {n}"
          f"   ({len(flagged) / n * 100:.1f}%)")
    print(f"  clean              {n - len(flagged)} / {n}\n")

    print("  latency (cold, no cache)")
    s = sorted(lat)
    print(f"    p50              {s[len(s) // 2]:.2f} ms")
    print(f"    p95              {s[int(len(s) * 0.95)]:.2f} ms")
    print(f"    max              {max(lat):.2f} ms")
    over = [x for x in lat if x > 50]
    print(f"    over 50ms        {len(over)}"
          f"{'  <-- would trip the watchdog' if over else ''}\n")

    if classes:
        print("  findings by class (incl. advisory)")
        for c, k in classes.most_common():
            print(f"    {c:24} {k}")
        print()

    if flagged:
        print(f"  BLOCKED TURNS -- each needs a human call: true leak or false positive?")
        for i, f in enumerate(flagged, 1):
            print(f"    [{i}] {f['project'][:34]:36} {f['chars']:>7,} chars")
            print(f"        classes   {', '.join(f['classes'])}")
            print(f"        detectors {', '.join(f['detectors'])}")
            if args.show_shapes:
                for sh in f["shapes"]:
                    print(f"        shape     {sh}")
        print()
    else:
        print("  no turn was blocked.\n")


if __name__ == "__main__":
    main()
