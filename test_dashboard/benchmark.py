"""Run the corpus through the real gateway pipeline and grade the result.

This imports the product. It does not reimplement it. Every record goes through the
same objects a live request goes through:

    SpanTree(body, extract_spans(body))      gateway/spans/jsonspan.py
    Checker._scan_all -> _verdict            gateway/base/checker.py
    StubPolicyClient.decide                  gateway/base/policy.py
    plan_redaction -> apply -> verify        gateway/redact.py

**One deliberate substitution, disclosed.** `Checker.check()` dispatches the scan to a
worker thread so a 50ms watchdog can bound it -- CPU-bound Python cannot be interrupted
from outside. That is a latency-safety mechanism, not a detection mechanism, and paying
a thread hop five million times would measure the executor rather than the detector. So
the sweep calls `_scan_all` and `_verdict` directly, and a separate sample pass
(`--async-sample`) runs the full `check()` including the hop, so the cost of the thing
that was skipped is measured rather than assumed.

**Nothing sensitive leaves the run.** The corpus generates synthetic values, and the
sample records written for the console carry span paths, classes and offsets -- the
same fields `Finding` allows and nothing more. `verify_dispatch` runs on every
redacting record, so the "redacted" count is a proven count and not a claimed one.

    python test_dashboard/benchmark.py --records 5000000 --workers 20
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.path.insert(0, str(Path(__file__).resolve().parent))

#: Families whose records are generated with no leak in them at all. An enforceable
#: finding on one of these is a false positive with no argument available -- which is
#: what makes them the only honest place to measure the false-positive rate.
QUIET_FAMILIES = frozenset({
    "clean_code", "clean_prose", "clean_agent_trace",
    "decoy_placeholder", "decoy_high_entropy", "decoy_near_miss_id",
    "composite_weak",
})

#: Latency histogram resolution. Scan times land between 10us and a few ms, so a 1us
#: bucket to 40ms gives exact percentiles without storing five million floats.
_LAT_BUCKETS = 40_000


def _drive(coro):
    """Run a coroutine that never awaits, without an event loop.

    `StubPolicyClient.decide` is `async def` for interface reasons and suspends at no
    point. Spinning up an event loop five million times to discover that would cost
    more than the policy decision itself. If it ever does await, this raises rather
    than silently returning None -- a policy decision that quietly became `None` would
    grade every record as `allow`.
    """
    try:
        coro.send(None)
    except StopIteration as stop:
        return stop.value
    coro.close()
    raise RuntimeError("policy decide() awaited; the fast driver is no longer valid")


# --------------------------------------------------------------------- per worker --

_STATE: dict = {}


def _init_worker() -> None:
    logging.disable(logging.CRITICAL)
    from gateway.base.budget import Deadline, ScanLimits
    from gateway.base.cache import InMemorySpanCache
    from gateway.base.checker import Checker, CheckerConfig
    from gateway.base.policy import StubPolicyClient
    from gateway.base.scanner import DetectorPack, _AC_NAME, _RE_NAME
    from gateway.contracts.types import Tier
    from gateway.detect.composite import scan_span_composite
    from gateway.detect.encodings import EncodedScanner
    from gateway.detect.obfuscation import ObfuscationScanner
    from gateway.detect.s0_credentials import scan_span_credentials
    from gateway.detect.s1_context import ContextScanner
    from gateway.detectors import ALL_DETECTORS

    detectors = list(ALL_DETECTORS)
    pack = DetectorPack.build(detectors, version=1, scanners=[
        scan_span_credentials,
        ObfuscationScanner(detectors),
        ContextScanner(),
        scan_span_composite,
        EncodedScanner(scan_span_credentials),
    ])
    # A real gateway keeps the span cache warm across a conversation. Here every record
    # is a different conversation, so the cache is left in place (it is part of the
    # pipeline) but it will mostly miss -- and the miss rate is reported rather than
    # tuned away.
    checker = Checker(pack, InMemorySpanCache(), tenant_key=b"benchmark-tenant-key",
                      config=CheckerConfig(ceiling_ms=50.0, max_tier=Tier.CONTEXT))
    _STATE.update(
        checker=checker, pack=pack, policy=StubPolicyClient(),
        Deadline=Deadline, limits=ScanLimits(), Tier=Tier,
        engines=f"{_AC_NAME}/{_RE_NAME}",
    )


def _blank() -> dict:
    return {
        "records": 0, "spans": 0, "bytes": 0,
        "scenario": Counter(), "verdict": Counter(), "action": Counter(),
        "status": Counter(), "cls": Counter(), "family": Counter(),
        "stage": Counter(), "detector": Counter(), "leg": Counter(),
        "origin_found": Counter(), "confidence": Counter(),
        "harness": Counter(), "route": Counter(), "provider": Counter(),
        "channel": Counter(), "env_action": Counter(), "actor_action": Counter(),
        "workload": Counter(), "span_path": Counter(),
        "recall_hit": Counter(), "recall_miss": Counter(),
        "variant_total": Counter(), "variant_blocked": Counter(),
        "variant_found": Counter(),
        "scenario_total": Counter(), "scenario_enforced": Counter(),
        "quiet_fp": Counter(), "quiet_records": 0, "quiet_fp_records": 0,
        "readonly_skipped": 0, "readonly_expected_enforced": 0,
        "degraded_formats": Counter(), "degraded": Counter(),
        "verify_failures": 0, "redactions": 0, "cache_hits": 0, "cache_misses": 0,
        "overlapping_redactions": 0, "collision_pairs": Counter(),
        "collision_records": 0,
        "credential_not_blocked": 0, "credential_records": 0,
        "advisory_findings": 0, "findings": 0,
        "latency_us": [0] * _LAT_BUCKETS, "latency_sum_us": 0.0,
        "latency_max_us": 0.0,
        "minute": Counter(), "minute_blocked": Counter(), "minute_redacted": Counter(),
        "samples": [],
    }


def _merge(into: dict, other: dict) -> dict:
    for key, value in other.items():
        if key == "latency_us":
            acc = into[key]
            for i, n in enumerate(value):
                if n:
                    acc[i] += n
        elif key == "samples":
            into[key].extend(value)
        elif isinstance(value, Counter):
            into[key].update(value)
        elif isinstance(value, (int, float)):
            if key == "latency_max_us":
                into[key] = max(into[key], value)
            else:
                into[key] += value
    return into


def _run_shard(args: tuple[int, int, int, int]) -> dict:
    """Scan one shard. Returns aggregate counters, never records."""
    shard_id, count, offset, sample_every = args
    if not _STATE:
        _init_worker()

    import corpus
    from gateway.contracts.entity_classes import family_of
    from gateway.contracts.types import Action
    from gateway.redact import (
        DispatchVerificationError, apply_redaction, plan_redaction, verify_dispatch,
    )
    from gateway.spans.jsonspan import MalformedJSON, extract_spans
    from gateway.spans.model import OverlappingEdits, SpanTree

    checker = _STATE["checker"]
    policy = _STATE["policy"]
    Deadline = _STATE["Deadline"]
    limits = _STATE["limits"]
    tier = _STATE["Tier"].CONTEXT
    out = _blank()
    lat = out["latency_us"]

    for rec in corpus.shard(shard_id, count, offset):
        body = json.dumps(rec.payload, separators=(",", ":")).encode("utf-8")
        out["records"] += 1
        out["bytes"] += len(body)
        out["scenario"][rec.scenario] += 1
        out["harness"][rec.harness] += 1
        out["route"][rec.route] += 1
        out["provider"][rec.provider] += 1
        out["channel"][rec.channel] += 1
        out["workload"][rec.workload] += 1
        out["leg"][rec.leg] += 1
        out["minute"][rec.ts_bucket] += 1

        try:
            tree = SpanTree(body, extract_spans(body), provider=rec.provider)
        except MalformedJSON:
            out["degraded"]["malformed_payload"] += 1
            continue

        origins = {s.path: s.origin for s in tree}
        out["spans"] += len(origins)

        # -- the scan, timed -------------------------------------------------------
        deadline = Deadline(ceiling_ms=50_000.0)   # the watchdog is measured separately
        t0 = time.perf_counter_ns()
        findings, hits, misses = checker._scan_all(tree, "bench", deadline, limits)
        check = checker._verdict(findings, t0 / 1e9, hits, misses)
        elapsed_us = (time.perf_counter_ns() - t0) / 1000.0

        bucket = int(elapsed_us)
        lat[bucket if bucket < _LAT_BUCKETS else _LAT_BUCKETS - 1] += 1
        out["latency_sum_us"] += elapsed_us
        out["latency_max_us"] = max(out["latency_max_us"], elapsed_us)
        out["cache_hits"] += hits
        out["cache_misses"] += misses
        out["verdict"][check.verdict.value] += 1
        if check.degraded:
            out["degraded"][check.degraded] += 1

        # -- what was found --------------------------------------------------------
        found_enforceable: set[str] = set()
        found_all: set[str] = set()
        for f in check.findings:
            cls = f.entity_class.value
            found_all.add(cls)
            out["findings"] += 1
            out["cls"][cls] += 1
            out["family"][family_of(f.entity_class).value] += 1
            out["stage"][f.stage] += 1
            out["detector"][f.detector_name or "(unnamed)"] += 1
            out["origin_found"][origins.get(f.span_path, "user")] += 1
            out["confidence"][round(f.confidence, 1)] += 1
            out["span_path"][f.span_path.split("$")[0][:48]] += 1
            if f.advisory_only:
                out["advisory_findings"] += 1
            else:
                found_enforceable.add(cls)

        # Which classes land on identical offsets, whatever the action turns out to be.
        # Recorded for every record, so the collision census is independent of whether
        # this particular one happened to reach the splice.
        at_offset: dict = {}
        for f in check.findings:
            at_offset.setdefault((f.span_path, f.start, f.end), []).append(f)
        collided = False
        for group in at_offset.values():
            enforceable = sorted({g.entity_class.value for g in group
                                  if not g.advisory_only})
            if len(enforceable) > 1:
                collided = True
                out["collision_pairs"]["+".join(enforceable)] += 1
        if collided:
            out["collision_records"] += 1

        # -- policy, redaction, and the proof --------------------------------------
        decision = _drive(policy.decide(
            actor=_actor_of(rec), findings=check.findings, risk=check.risk,
            leg=rec.leg, destination=rec.provider, origins=origins))
        out["action"][decision.action.value] += 1
        out["env_action"][f"{rec.env}:{decision.action.value}"] += 1
        out["actor_action"][f"{rec.actor[1]}:{decision.action.value}"] += 1

        status = "clean"
        plan = None
        if decision.action is Action.BLOCK:
            status = "blocked"
        elif decision.action in (Action.TOKENIZE, Action.MASK):
            plan = plan_redaction(tree, check.findings, decision,
                                  tenant_key=b"benchmark-tenant-key",
                                  scope_key=f"sess_{rec.index % 4096}")
            try:
                dispatched = apply_redaction(tree, plan)
                verify_dispatch(dispatched, plan)
                status = "redacted" if plan.redactions else "clean"
                out["redactions"] += len(plan.redactions)
            except OverlappingEdits:
                # Two enforceable findings claimed the same offsets -- AADHAAR beside
                # QUASI_IDENTIFIER_SET, or an S0 credential beside the S1 key-name rule
                # that named the same value. `plan_redaction` emits one edit per finding
                # and does not merge them, so the splice refuses the pair. Counted, not
                # swallowed: how often this happens across five million records is the
                # measurement, and `gateway/app.py::_run` does not catch it at all.
                out["overlapping_redactions"] += 1
                status = "blocked"
            except DispatchVerificationError:
                out["verify_failures"] += 1
                status = "blocked"
            for cls in plan.degraded_formats:
                out["degraded_formats"][cls.value] += 1
            out["readonly_skipped"] += len(plan.skipped_read_only)
        else:
            plan = plan_redaction(tree, check.findings, decision,
                                  tenant_key=b"benchmark-tenant-key",
                                  scope_key=f"sess_{rec.index % 4096}")
            out["readonly_skipped"] += len(plan.skipped_read_only)

        out["status"][status] += 1
        if status == "blocked":
            out["minute_blocked"][rec.ts_bucket] += 1
        elif status == "redacted":
            out["minute_redacted"][rec.ts_bucket] += 1

        # -- grading ----------------------------------------------------------------
        for cls in rec.expect:
            if cls in found_all:
                out["recall_hit"][cls] += 1
            else:
                out["recall_miss"][cls] += 1

        if rec.scenario in QUIET_FAMILIES:
            out["quiet_records"] += 1
            if found_enforceable:
                out["quiet_fp_records"] += 1
                for cls in found_enforceable:
                    out["quiet_fp"][cls] += 1

        if rec.expect_readonly:
            # A tool schema must never drive enforcement, whatever is written in it.
            if decision.action is Action.BLOCK:
                out["readonly_expected_enforced"] += 1

        if rec.expect_action == "block":
            out["credential_records"] += 1
            if decision.action is not Action.BLOCK:
                out["credential_not_blocked"] += 1

        # Recall per evasion style. `cred_obfuscated` as one number hides which trick
        # actually works, and which trick works is the only actionable half.
        if rec.variant:
            key = f"{rec.scenario}:{rec.variant}"
            out["variant_total"][key] += 1
            if decision.action is Action.BLOCK:
                out["variant_blocked"][key] += 1
            if rec.expect & found_all:
                out["variant_found"][key] += 1

        out["scenario_total"][rec.scenario] += 1
        if status in ("blocked", "redacted"):
            out["scenario_enforced"][rec.scenario] += 1

        # -- a thin, safe slice for the console -------------------------------------
        if rec.index % sample_every == 0 and len(out["samples"]) < 600:
            out["samples"].append(_sample(rec, check, decision, plan, status,
                                          elapsed_us, origins))

    return out


def _actor_of(rec):
    from gateway.contracts.types import Actor
    aid, role, groups = rec.actor
    return Actor(id=aid, tenant_id="bench", role=role, groups=tuple(groups),
                 channel=rec.channel, session_id=f"sess_{rec.index % 4096}")


def _sample(rec, check, decision, plan, status, elapsed_us, origins) -> dict:
    """One console row. Paths, classes and offsets -- never a value."""
    return {
        "id": f"req_{rec.index:08X}",
        "scenario": rec.scenario,
        "variant": rec.variant,
        "minute": rec.ts_bucket,
        "actor": {"id": rec.actor[0], "role": rec.actor[1],
                  "groups": list(rec.actor[2]),
                  "unregistered": rec.actor[1] == "unregistered"},
        "workload": rec.workload,
        "harness": rec.harness,
        "channel": rec.channel,
        "env": rec.env,
        "provider": rec.provider,
        "route": rec.route,
        "leg": rec.leg,
        "status": status,
        "action": decision.action.value,
        "verdict": check.verdict.value,
        "rule_index": decision.rule_index,
        "latency_us": round(elapsed_us, 1),
        "degraded": check.degraded,
        "cache_hits": check.cache_hits,
        "cache_misses": check.cache_misses,
        "readonly_skipped": len(plan.skipped_read_only) if plan else 0,
        "findings": [
            {"span_path": f.span_path, "class": f.entity_class.value,
             "confidence": round(f.confidence, 3), "stage": f.stage,
             "start": f.start, "end": f.end, "length": f.end - f.start,
             "detector": f.detector_name, "advisory": f.advisory_only,
             "origin": origins.get(f.span_path, "user"), "leg": f.leg}
            for f in check.findings[:8]
        ],
    }


# ------------------------------------------------------------------- percentiles --

def _quantile(hist: list[int], q: float) -> float:
    total = sum(hist)
    if not total:
        return 0.0
    target = q * total
    seen = 0
    for i, n in enumerate(hist):
        seen += n
        if seen >= target:
            return i + 0.5
    return float(len(hist))


# -------------------------------------------------------------- the async sample --

def _async_sample(n: int) -> dict:
    """Measure the real `Checker.check()`, thread hop and watchdog included."""
    import asyncio
    import corpus
    if not _STATE:
        _init_worker()
    checker = _STATE["checker"]
    from gateway.spans.jsonspan import extract_spans
    from gateway.spans.model import SpanTree

    async def go():
        lat: list[float] = []
        for rec in corpus.shard(9_999, n, 0):
            body = json.dumps(rec.payload, separators=(",", ":")).encode()
            try:
                tree = SpanTree(body, extract_spans(body), provider=rec.provider)
            except Exception:
                continue
            t0 = time.perf_counter_ns()
            await checker.check(tree, "bench")
            lat.append((time.perf_counter_ns() - t0) / 1000.0)
        return lat

    lat = sorted(asyncio.run(go()))
    if not lat:
        return {}
    def q(p): return lat[min(len(lat) - 1, int(p * len(lat)))]
    return {"records": len(lat), "p50_us": q(.50), "p95_us": q(.95),
            "p99_us": q(.99), "max_us": lat[-1],
            "mean_us": sum(lat) / len(lat)}


# ------------------------------------------------------- per-detector micro-bench --

def _detector_costs(reps: int = 3000) -> dict:
    """Isolated cost per detector, so the console can show a real runtime column."""
    if not _STATE:
        _init_worker()
    import random
    import corpus
    from gateway.base.budget import Deadline
    from gateway.spans.model import Span

    rng = random.Random(7)
    out: dict[str, dict] = {}
    probes = {
        "ANTHROPIC_KEY": corpus.CRED_SHAPES["ANTHROPIC_KEY"],
        "OPENAI_KEY": corpus.CRED_SHAPES["OPENAI_KEY"],
        "GITHUB_TOKEN": corpus.CRED_SHAPES["GITHUB_TOKEN"],
        "AWS_ACCESS_KEY": corpus.CRED_SHAPES["AWS_ACCESS_KEY"],
        "RAZORPAY_KEY": corpus.CRED_SHAPES["RAZORPAY_KEY"],
        "SLACK_TOKEN": corpus.CRED_SHAPES["SLACK_TOKEN"],
        "GOOGLE_API_KEY": corpus.CRED_SHAPES["GOOGLE_API_KEY"],
        "STRIPE_KEY": corpus.CRED_SHAPES["STRIPE_KEY"],
        "JWT": corpus.CRED_SHAPES["JWT"],
        "PRIVATE_KEY": corpus.CRED_SHAPES["PRIVATE_KEY"],
        "DB_URI": corpus.CRED_SHAPES["DB_URI"],
        "PAN": corpus._pan,
        "AADHAAR": corpus._aadhaar,
        "GSTIN": corpus._gstin,
        "IFSC": corpus._ifsc,
        "UPI_VPA": corpus._upi,
        "VOTER_ID": corpus._voter,
    }
    from gateway.detect.s0_credentials import scan_span_credentials
    from gateway.base.scanner import scan_span
    pack = _STATE["pack"]
    limits = _STATE["limits"]
    tier = _STATE["Tier"].CONTEXT

    for cls, maker in probes.items():
        text = f"the value on file is {maker(rng)} please verify it"
        span = Span(path="p", text=text, origin="user", leg="outbound",
                    byte_start=0, byte_end=len(text.encode()))
        dl = Deadline(ceiling_ms=1e9)
        scan_span(span, pack, dl, limits, max_tier=tier)      # warm
        t0 = time.perf_counter_ns()
        for _ in range(reps):
            found = scan_span(span, pack, dl, limits, max_tier=tier)
        ns = (time.perf_counter_ns() - t0) / reps
        out[cls] = {"runtime_us": round(ns / 1000.0, 3),
                    "hit": any(f.entity_class.value == cls for f in found),
                    "names": sorted({f.detector_name for f in found if f.detector_name})}
    return out


# ------------------------------------------------------------------------- main --

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=int, default=5_000_000)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--shards", type=int, default=0)
    ap.add_argument("--async-sample", type=int, default=20_000)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "results"))
    args = ap.parse_args()

    total = args.records
    workers = max(1, args.workers)
    shards = args.shards or workers * 8
    per = math.ceil(total / shards)
    jobs = []
    offset = 0
    remaining = total
    for k in range(shards):
        n = min(per, remaining)
        if n <= 0:
            break
        jobs.append((k, n, offset, max(1, total // 500)))
        offset += n
        remaining -= n

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"corpus mix sums to {__import__('corpus').mix_check():.4f}")
    print(f"running {total:,} records across {workers} workers "
          f"in {len(jobs)} shards of ~{per:,}")

    started = time.time()
    agg = _blank()
    done = 0
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as pool:
        for result in pool.map(_run_shard, jobs, chunksize=1):
            _merge(agg, result)
            done += 1
            elapsed = time.time() - started
            rate = agg["records"] / elapsed if elapsed else 0
            print(f"  shard {done}/{len(jobs)}  {agg['records']:>9,} records  "
                  f"{rate:>9,.0f} rec/s  {elapsed:>6.1f}s", flush=True)
    wall = time.time() - started

    print("measuring the async path (thread hop + watchdog)...")
    _init_worker()
    async_stats = _async_sample(args.async_sample)
    print("measuring per-detector cost...")
    det_costs = _detector_costs()

    report = _report(agg, wall, async_stats, det_costs, workers)
    (outdir / "metrics.json").write_text(
        json.dumps(report, indent=2, sort_keys=False), encoding="utf-8")
    samples = agg["samples"][:600]
    (outdir / "samples.json").write_text(
        json.dumps(samples, indent=2), encoding="utf-8")

    print(f"\nwrote {outdir / 'metrics.json'} and {outdir / 'samples.json'}")
    print(f"{agg['records']:,} records in {wall:.1f}s "
          f"({agg['records'] / wall:,.0f}/s), {agg['findings']:,} findings")
    return 0


def _report(agg: dict, wall: float, async_stats: dict, det_costs: dict,
            workers: int) -> dict:
    hist = agg["latency_us"]
    records = agg["records"] or 1

    recall = {}
    for cls in sorted(set(agg["recall_hit"]) | set(agg["recall_miss"])):
        hit = agg["recall_hit"][cls]
        miss = agg["recall_miss"][cls]
        fp = agg["quiet_fp"][cls]
        recall[cls] = {
            "expected": hit + miss, "found": hit, "missed": miss,
            "recall": round(hit / (hit + miss), 6) if (hit + miss) else None,
            "false_positives_on_quiet": fp,
            "precision_vs_quiet": round(hit / (hit + fp), 6) if (hit + fp) else None,
            "runtime_us": det_costs.get(cls, {}).get("runtime_us"),
            "detectors": det_costs.get(cls, {}).get("names", []),
        }

    quiet = agg["quiet_records"] or 1
    return {
        "meta": {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "records": agg["records"],
            "spans_scanned": agg["spans"],
            "bytes_scanned": agg["bytes"],
            "wall_seconds": round(wall, 2),
            "records_per_second": round(agg["records"] / wall, 1) if wall else None,
            "workers": workers,
            "engines": _STATE.get("engines", "unknown"),
            "corpus_seed": __import__("corpus").SEED,
            "note": ("Synthetic corpus. Scan measured without the worker-thread hop; "
                     "the async sample below measures that separately."),
        },
        "latency_us": {
            "p50": _quantile(hist, .50), "p90": _quantile(hist, .90),
            "p95": _quantile(hist, .95), "p99": _quantile(hist, .99),
            "p999": _quantile(hist, .999),
            "mean": round(agg["latency_sum_us"] / records, 2),
            "max": round(agg["latency_max_us"], 1),
        },
        "latency_async_us": async_stats,
        "throughput": {
            "spans_per_record": round(agg["spans"] / records, 2),
            "bytes_per_record": round(agg["bytes"] / records, 1),
            "mb_per_second": round(agg["bytes"] / 1e6 / wall, 1) if wall else None,
        },
        "outcomes": {
            "status": dict(agg["status"]),
            "action": dict(agg["action"]),
            "verdict": dict(agg["verdict"]),
            "findings_total": agg["findings"],
            "advisory_findings": agg["advisory_findings"],
            "redactions_verified": agg["redactions"],
            "verify_failures": agg["verify_failures"],
            "overlapping_redactions": agg["overlapping_redactions"],
            "readonly_findings_skipped": agg["readonly_skipped"],
            "cache_hits": agg["cache_hits"],
            "cache_misses": agg["cache_misses"],
        },
        "integrity": {
            "credential_records": agg["credential_records"],
            "credential_not_blocked": agg["credential_not_blocked"],
            "credential_block_rate": round(
                1 - agg["credential_not_blocked"] / (agg["credential_records"] or 1), 6),
            "tool_definition_enforced": agg["readonly_expected_enforced"],
            "quiet_records": agg["quiet_records"],
            "quiet_false_positive_records": agg["quiet_fp_records"],
            "false_positive_rate": round(agg["quiet_fp_records"] / quiet, 8),
        },
        "by_class": dict(agg["cls"].most_common()),
        "by_family": dict(agg["family"].most_common()),
        "by_stage": dict(agg["stage"].most_common()),
        "by_detector": dict(agg["detector"].most_common()),
        "by_origin": dict(agg["origin_found"].most_common()),
        "by_confidence": {str(k): v for k, v in sorted(agg["confidence"].items())},
        "by_span_path": dict(agg["span_path"].most_common(24)),
        "detector_quality": recall,
        "degraded": dict(agg["degraded"]),
        "degraded_formats": dict(agg["degraded_formats"]),
        "offset_collisions": {
            "records": agg["collision_records"],
            "rate": round(agg["collision_records"] / records, 8),
            "reached_the_splice": agg["overlapping_redactions"],
            "pairs": dict(agg["collision_pairs"].most_common(20)),
        },
        "scenarios": dict(agg["scenario"].most_common()),
        "scenario_enforcement": {
            name: {
                "records": total,
                "enforced": agg["scenario_enforced"][name],
                "rate": round(agg["scenario_enforced"][name] / total, 6) if total else None,
            }
            for name, total in agg["scenario_total"].most_common()
        },
        "evasion": {
            key: {
                "records": total,
                "detected": agg["variant_found"][key],
                "blocked": agg["variant_blocked"][key],
                "detection_rate": round(agg["variant_found"][key] / total, 6),
                "block_rate": round(agg["variant_blocked"][key] / total, 6),
            }
            for key, total in sorted(agg["variant_total"].items())
        },
        "coverage": {
            "harness": dict(agg["harness"].most_common()),
            "route": dict(agg["route"].most_common()),
            "provider": dict(agg["provider"].most_common()),
            "channel": dict(agg["channel"].most_common()),
            "workload": dict(agg["workload"].most_common()),
        },
        "environments": dict(agg["env_action"]),
        "by_actor_role": dict(agg["actor_action"]),
        "timeline": {
            "minute": {str(k): v for k, v in sorted(agg["minute"].items())},
            "blocked": {str(k): v for k, v in sorted(agg["minute_blocked"].items())},
            "redacted": {str(k): v for k, v in sorted(agg["minute_redacted"].items())},
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
