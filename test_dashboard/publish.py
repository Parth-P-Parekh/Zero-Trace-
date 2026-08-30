"""Move the benchmark result into the web app, in the shape the console reads.

Two files go in, two come out. `metrics.json` is the aggregate and `samples.json`
is a thin slice of real request rows; both are rewritten here into
`app/web/src/data/` with the derived series the views need, so no view has to do
arithmetic on a five-million-record summary at render time.

Nothing is invented in this step. Every number written is either copied from the
run or computed from numbers in the run, and anything the run did not measure is
written as `null` so the interface can say so rather than imply a value.

    python test_dashboard/publish.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
OUT = HERE.parent / "app" / "web" / "src" / "data"

#: The six-stop opacity ramp is the design system's only source of tonal value, so
#: series that will be drawn with it are pre-bucketed to six stops here rather than
#: each view inventing its own scale.
RAMP = (1.0, 0.72, 0.52, 0.36, 0.22, 0.11)


def ramp_stop(fraction: float) -> float:
    """Nearest ramp stop for a 0-1 value. Keeps every drawn fill on the ramp."""
    return min(RAMP, key=lambda stop: abs(stop - fraction))


def main() -> int:
    metrics = json.loads((RESULTS / "metrics.json").read_text(encoding="utf-8"))
    samples = json.loads((RESULTS / "samples.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)

    records = metrics["meta"]["records"]
    outcomes = metrics["outcomes"]
    status = outcomes["status"]

    # -- the traffic timeline, folded from minute buckets into 24 hours ------------
    hours = [{"hour": h, "total": 0, "blocked": 0, "redacted": 0} for h in range(24)]
    for key, value in metrics["timeline"]["minute"].items():
        hours[int(key) // 60]["total"] += value
    for key, value in metrics["timeline"]["blocked"].items():
        hours[int(key) // 60]["blocked"] += value
    for key, value in metrics["timeline"]["redacted"].items():
        hours[int(key) // 60]["redacted"] += value
    peak = max(h["total"] for h in hours) or 1
    for h in hours:
        h["share"] = round(h["total"] / peak, 4)
        h["clean"] = h["total"] - h["blocked"] - h["redacted"]

    # -- environments: production enforces, staging observes ----------------------
    envs: dict[str, dict] = {}
    for key, count in metrics["environments"].items():
        env, action = key.split(":", 1)
        envs.setdefault(env, {"actions": {}, "records": 0})
        envs[env]["actions"][action] = count
        envs[env]["records"] += count
    for env, block in envs.items():
        acts = block["actions"]
        total = block["records"] or 1
        block["would_block"] = acts.get("block", 0)
        block["would_redact"] = acts.get("tokenize", 0) + acts.get("mask", 0)
        block["allowed"] = acts.get("allow", 0) + acts.get("warn", 0)
        block["intervention_rate"] = round(
            (block["would_block"] + block["would_redact"]) / total, 6)
        # Staging runs the same policy without enforcing it. The decision is
        # identical; what differs is whether it is applied -- which is the only
        # honest way to describe shadow mode.
        block["mode"] = "enforce" if env == "production" else "shadow"

    # -- detector table, ordered by what a reader should look at first ------------
    detectors = []
    for cls, q in metrics["detector_quality"].items():
        recall = q["recall"]
        precision = q["precision_vs_quiet"]
        f1 = (2 * recall * precision / (recall + precision)
              if recall and precision else None)
        detectors.append({
            "entityClass": cls,
            "expected": q["expected"],
            "found": q["found"],
            "missed": q["missed"],
            "recall": recall,
            "precision": precision,
            "f1": round(f1, 6) if f1 else None,
            "falsePositives": q["false_positives_on_quiet"],
            "runtimeUs": q["runtime_us"],
            "detectors": q["detectors"],
            "observed": metrics["by_class"].get(cls, 0),
        })
    # Weakest first: a registry sorted alphabetically buries the one row that needs
    # a decision. Nulls last, because "not measured" is not "worst".
    detectors.sort(key=lambda d: (d["recall"] is None, d["recall"] or 0))

    # -- evasion matrix -----------------------------------------------------------
    evasion = []
    for key, v in metrics["evasion"].items():
        family, variant = key.split(":", 1)
        evasion.append({
            "family": family, "variant": variant,
            "records": v["records"],
            "detectionRate": v["detection_rate"],
            "blockRate": v["block_rate"],
            "ramp": ramp_stop(v["detection_rate"]),
        })
    evasion.sort(key=lambda e: e["detectionRate"])

    classes = metrics["by_class"]
    class_total = sum(classes.values()) or 1

    console = {
        "meta": metrics["meta"],
        "latency": metrics["latency_us"],
        "latencyAsync": metrics["latency_async_us"],
        "throughput": metrics["throughput"],
        "outcomes": outcomes,
        "integrity": metrics["integrity"],
        "status": {
            "clean": status.get("clean", 0),
            "redacted": status.get("redacted", 0),
            "blocked": status.get("blocked", 0),
            "total": records,
        },
        "actions": metrics["outcomes"]["action"],
        "verdicts": metrics["outcomes"]["verdict"],
        "byClass": [
            {"entityClass": k, "count": v, "share": round(v / class_total, 6)}
            for k, v in classes.items()
        ],
        "byFamily": [
            {"family": k, "count": v,
             "share": round(v / (sum(metrics["by_family"].values()) or 1), 6)}
            for k, v in metrics["by_family"].items()
        ],
        "byStage": metrics["by_stage"],
        "byOrigin": metrics["by_origin"],
        "byConfidence": metrics["by_confidence"],
        "bySpanPath": metrics["by_span_path"],
        "byDetector": metrics["by_detector"],
        "detectors": detectors,
        "evasion": evasion,
        "collisions": metrics["offset_collisions"],
        "degraded": metrics["degraded"],
        "degradedFormats": metrics["degraded_formats"],
        "coverage": metrics["coverage"],
        "environments": envs,
        "byActorRole": metrics["by_actor_role"],
        "scenarios": metrics["scenarios"],
        "scenarioEnforcement": metrics["scenario_enforcement"],
        "hours": hours,
    }

    (OUT / "benchmark.json").write_text(
        json.dumps(console, indent=1), encoding="utf-8")
    (OUT / "samples.json").write_text(
        json.dumps(samples[:400], indent=1), encoding="utf-8")

    print(f"wrote {OUT / 'benchmark.json'} ({(OUT / 'benchmark.json').stat().st_size:,} bytes)")
    print(f"wrote {OUT / 'samples.json'} ({(OUT / 'samples.json').stat().st_size:,} bytes)")
    print(f"records {records:,} · detectors {len(detectors)} · evasion rows {len(evasion)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
