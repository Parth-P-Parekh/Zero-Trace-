"""Our detector, wearing Part A's interface.

Agenda Task 3. Part A declares the seam in `zerotrace.detect.stub`:

    async def scan(self, payload: dict, leg: Leg) -> list[Finding]

and ships a `StubDetector` that finds nothing and says so. This is the thing that replaces
it. Part A keeps answering *who is asking* and *what the rule says*; this answers *what is
in the text*, which is the half it deliberately did not build.

**Nothing is reimplemented here.** The payload goes through the same `extract_spans`
normaliser and the same `Checker` the hooks use, so the control plane sees exactly what
the side-car sees. A second detection path would be a second set of answers, and the one
that mattered would be whichever the demo happened to exercise.

**The conversion drops more than it carries, on purpose.** Their `Finding` has fields ours
does not — `token`, `adjudicated`, `exception_applied` — and every one of them is decided
by *policy*, not by detection. Filling them here would be the detector claiming authority
over decisions that are Part A's to make, so they keep their defaults.

**Advisory findings are withheld from policy and sent to Loop 2 instead.** Our `Finding`
carries `advisory_only`, and the contract names `HIGH_ENTROPY_STRING` in
`NEVER_ENFORCE_ALONE`: a 0.55-confidence entropy hit is corroboration, never grounds to
act. Part A's `Finding` has no field for that, so anything sent across arrives looking
enforceable — forwarding it unmarked would offer the policy engine a reason to block that
we do not stand behind.

But it is not noise, and dropping it would waste the most interesting signal we have. A
high-entropy run that no detector claimed is exactly what a novel credential, an encoding
we do not decode, or an attempt to smuggle something past the rules looks like. So it goes
to the intel plane, which is blind by construction: `EscalationFeatures` carries a shape,
a length, a charset and an entropy score, never the text. Loop 2 proposes *additional
checks for later calls*; it cannot gate this one, and it never sees the prompt.

This is inbound-side protection — it guards what reaches the model, not what the model
says back. `include_advisory=True` still forwards them to policy for a caller who knows
what it is asking for.

Neither `Finding` has ever carried the matched value, and that survives the conversion:
what crosses is a class, a path, offsets and a confidence.
"""

from __future__ import annotations

import json
from typing import Any

from gateway.spans.jsonspan import MalformedJSON, extract_spans


class RootDetector:
    """Part A's `Detector`, backed by the root S0-S3 stack."""

    name = "zerotrace-root"

    #: No degradation to report: this is the real detector. Part A puts this string in a
    #: response header and in the ledger, and `None` is how it says the scan was genuine.
    degrade_reason: str | None = None

    __slots__ = ("_check", "_min_confidence", "_include_advisory", "_intel", "_key")

    def __init__(
        self,
        check: Any = None,
        *,
        min_confidence: float = 0.0,
        include_advisory: bool = False,
        intel: Any = None,
    ) -> None:
        self._check = check
        self._min_confidence = min_confidence
        self._include_advisory = include_advisory
        self._intel = intel
        self._key: bytes | None = None

    # -- the seam --

    async def scan(self, payload: dict, leg: str) -> list[Any]:
        findings, spans = await self._scan_root(payload, leg)
        kept, withheld = convert(
            findings, leg,
            include_advisory=self._include_advisory,
            min_confidence=self._min_confidence,
        )
        escalate(self._intel, withheld, spans, findings, self._tenant_key())
        return kept

    # -- loop 2 --

    def _tenant_key(self) -> bytes:
        import os

        if self._key is None:
            self._key = os.environ.get("ZT_VAULT_MASTER_KEY", "dev-key").encode()
        return self._key

    # -- the root scan --

    async def _scan_root(self, payload: dict, leg: str) -> tuple[list[Any], list[Any]]:
        checker = self._check or _default_checker()
        raw = json.dumps(payload).encode("utf-8")
        try:
            spans = extract_spans(raw, leg=leg)
        except MalformedJSON:
            # A body we cannot parse is not a body we can clear. Part A's caller decides
            # what to do with an empty finding list plus a degrade reason; inventing
            # findings here would be worse, and so would claiming a clean scan.
            self.degrade_reason = "payload_unparseable"
            return [], []

        tree = _tree(raw, spans, leg)
        result = await checker.check(tree, "part-a")
        return list(getattr(result, "findings", ()) or ()), spans


def convert(
    findings: list[Any], leg: str, *, include_advisory: bool = False,
    min_confidence: float = 0.0,
) -> tuple[list[Any], list[Any]]:
    """Root findings -> Part A findings, plus the ones withheld.

    **The single conversion.** `RootDetector.scan` and the HTTP gate both call this,
    because two copies of these rules would be two answers to "is this enforceable", and
    the one that mattered would be whichever path the request happened to take. An earlier
    version had exactly that: a duplicate in `app.py` that dropped advisory findings and
    forgot to escalate them, so the intel plane saw nothing from real traffic.
    """
    from zerotrace.spans.model import Finding as PartAFinding

    kept: list[Any] = []
    withheld: list[Any] = []
    for f in findings:
        if f.confidence < min_confidence:
            continue
        if getattr(f, "advisory_only", False) and not include_advisory:
            withheld.append(f)
            continue
        kept.append(
            PartAFinding(
                entity_class=_class_value(f.entity_class),
                span_path=f.span_path,
                leg=leg,  # type: ignore[arg-type]
                confidence=float(f.confidence),
                detector_id=getattr(f, "detector_id", None),
                stage=getattr(f, "stage", "S0"),
                start=int(getattr(f, "start", 0) or 0),
                end=int(getattr(f, "end", 0) or 0),
            )
        )
    return kept, withheld


def escalate(intel: Any, withheld: list[Any], spans: list[Any], all_findings: list[Any],
             tenant_key: bytes) -> None:
    """Hand the shape of each withheld finding to the blind agent.

    Never awaited and never on the decision path: `maybe_escalate` enqueues and returns,
    and Loop 2 proposes checks for *later* calls. A model round trip is 300-2000ms and
    this sits in front of every request.
    """
    if not withheld or intel is None:
        return
    try:
        from gateway.intel.features import features_of

        by_path = {s.path: s for s in spans}
        for f in withheld:
            span = by_path.get(f.span_path)
            if span is None:
                continue
            intel.maybe_escalate(
                features_of(span, (f,), tenant_key,
                            neighbours=tuple(
                                o.entity_class for o in all_findings if o is not f
                            ))
            )
    except Exception:  # noqa: BLE001
        # Losing an escalation costs a future improvement, never this request.
        pass


def _class_value(entity_class: Any) -> str:
    """Their vocabulary is the string form of ours; both sides validate it."""
    return getattr(entity_class, "value", str(entity_class))


def _tree(raw: bytes, spans: list[Any], leg: str):
    """The tree keeps the original bytes: edits are recorded against them, never applied
    in place, so the redaction plan Part A may later ask for stays possible."""
    from gateway.spans.model import SpanTree

    return SpanTree(raw, list(spans), provider="part-a", leg=leg)


def _default_checker():
    """The same checker the hooks build, assembled once."""
    import os

    from gateway.base.cache import NullSpanCache
    from gateway.base.checker import Checker, CheckerConfig
    from gateway.base.scanner import DetectorPack
    from gateway.detect.encodings import EncodedScanner
    from gateway.detect.obfuscation import ObfuscationScanner
    from gateway.detect.s0_credentials import scan_span_credentials
    from gateway.detect.composite import scan_span_composite
    from gateway.detect.s1_context import ContextScanner
    from gateway.detectors import ALL_DETECTORS

    global _CHECKER
    if _CHECKER is None:
        detectors = list(ALL_DETECTORS)
        pack = DetectorPack.build(
            detectors, version=1,
            scanners=[scan_span_credentials, ObfuscationScanner(detectors),
                      ContextScanner(), scan_span_composite,
                  EncodedScanner(scan_span_credentials)],
        )
        _CHECKER = Checker(
            pack, NullSpanCache(),
            os.environ.get("ZT_VAULT_MASTER_KEY", "dev-key").encode(),
            CheckerConfig.from_env(),
        )
    return _CHECKER


_CHECKER = None
