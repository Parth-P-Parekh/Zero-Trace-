from __future__ import annotations
import os, sys, json, asyncio, time
sys.path.insert(0, os.path.expanduser("~/zt"))
from gateway.base.scanner import DetectorPack
from gateway.base.checker import Checker, CheckerConfig
from gateway.base.cache import InMemorySpanCache, NullSpanCache
from gateway.spans.jsonspan import extract_spans
from gateway.spans.model import SpanTree

def build_pack():
    from gateway.detectors import ALL_DETECTORS
    from gateway.detect.s0_credentials import scan_span_credentials
    from gateway.detect.obfuscation import ObfuscationScanner
    from gateway.detect.s1_context import ContextScanner
    from gateway.detect.composite import scan_span_composite
    from gateway.detect.encodings import EncodedScanner
    return DetectorPack.build(
        list(ALL_DETECTORS), version=1,
        scanners=[scan_span_credentials, ObfuscationScanner(list(ALL_DETECTORS)),
                  ContextScanner(), scan_span_composite,
                  EncodedScanner(scan_span_credentials)],
    )

def tree_of(payload: dict, leg="outbound") -> SpanTree:
    raw = json.dumps(payload).encode()
    return SpanTree(raw, extract_spans(raw, leg=leg), provider="anthropic", leg=leg)

def make_checker(cache=None, ceiling=50.0, key=b"stress-key"):
    return Checker(build_pack(), cache if cache is not None else InMemorySpanCache(),
                   tenant_key=key, config=CheckerConfig(ceiling_ms=ceiling))

async def check(ck, payload, leg="outbound", tenant="t1"):
    return await ck.check(tree_of(payload, leg), tenant)
