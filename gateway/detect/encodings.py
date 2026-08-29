"""Credentials hidden by an encoding. CODE-01 §19.3.

A key that has been base64'd is invisible to every pattern we have, and base64 is not an
attack -- it is how Kubernetes Secrets are stored, how HTTP Basic auth works, and what
PowerShell's ``[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($key))`` emits.
Someone pasting a Secret manifest is pasting encoded credentials with no intent to evade
anything.

**Scope is deliberately limited to encodings that occur without intent.** base64,
base64url, hex, percent-encoding and unicode escapes all appear in ordinary payloads.
ROT13, Caesar shifts, reversal and XOR do not -- nobody stores a key that way by
accident, so the only thing supporting them buys is a slightly harder puzzle for someone
who was always going to find an encoding we do not check. N encodings at depth k costs
N^k rescans, and an adversary composes faster than we enumerate. Deliberate evasion is
the coverage monitor's problem (C21) and the audit trail's, not a decoder's.

Three properties keep this affordable and safe:

* **Candidates only.** A region has to look like the encoding -- a long charset run, or
  actual ``%XX`` sequences -- before anything is decoded. Whole spans are never decoded.
* **Same bar.** The decoded text goes through the *real* S0 scanner. No new thresholds,
  no new classes, no lowered confidence. Decoding widens what we look at; it does not
  change what counts.
* **Depth 2.** ``base64(json({"key": "sk-ant-..."}))`` is a real shape worth catching.
  Deeper is adversarial, and that is where this stops.

**Findings cover the whole encoded region, not a slice of it.** Redacting part of a
base64 blob leaves a corrupt blob that still decodes to most of the key, so the unit of
redaction is the entire run.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass

from ..contracts.types import Finding
from ..spans.model import Span

log = logging.getLogger(__name__)

#: A decoded blob shorter than this cannot hold a credential worth reporting.
_MIN_DECODED = 20

#: Minimum length of an encoded run before it is worth decoding. Below this the decode
#: costs more than it can find, and short base64-ish runs are everywhere in code.
_MIN_RUN = 32

#: Ceiling on one encoded region, so a multi-megabyte embedded image cannot dominate the
#: scan. A credential does not need 8KB of base64 to hide in.
_MAX_REGION = 8192

#: Ceiling on candidates examined per span. A payload full of base64 (a notebook with
#: embedded images, say) must not turn into thousands of decodes.
_MAX_CANDIDATES = 24

# Built by concatenation rather than %-formatting: these patterns contain a literal `%`
# (percent-encoding) and `{n,}` quantifiers, both of which collide with format specifiers.
_N = str(_MIN_RUN)
_B64_RUN = re.compile("[A-Za-z0-9+/]{" + _N + ",}={0,2}")
_B64URL_RUN = re.compile("[A-Za-z0-9_-]{" + _N + ",}={0,2}")
_HEX_RUN = re.compile("(?:[0-9a-fA-F]{2}){20,}")
_PERCENT_RUN = re.compile("(?:%[0-9a-fA-F]{2}|[A-Za-z0-9._~-]){" + _N + ",}")
_UNICODE_RUN = re.compile(r"(?:\\u[0-9a-fA-F]{4}){10,}")


def _printable(s: str) -> bool:
    """Decoded output has to look like text. This is the main false-positive guard:
    random base64 usually decodes to bytes that are not printable at all."""
    if not s:
        return False
    printable = sum(1 for c in s if 32 <= ord(c) < 127 or c in "\t\n\r")
    return printable / len(s) > 0.9


def _b64(region: str) -> str | None:
    try:
        pad = "=" * (-len(region) % 4)
        raw = base64.b64decode(region + pad, validate=True)
    except (binascii.Error, ValueError):
        return None
    return _as_text(raw)


def _b64url(region: str) -> str | None:
    try:
        pad = "=" * (-len(region) % 4)
        raw = base64.urlsafe_b64decode(region + pad)
    except (binascii.Error, ValueError):
        return None
    return _as_text(raw)


def _hex(region: str) -> str | None:
    try:
        raw = bytes.fromhex(region)
    except ValueError:
        return None
    return _as_text(raw)


def _percent(region: str) -> str | None:
    if "%" not in region:
        return None
    out = urllib.parse.unquote(region)
    return out if out != region else None


def _unicode_escapes(region: str) -> str | None:
    try:
        out = region.encode("ascii", "ignore").decode("unicode_escape")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return None
    return out if out != region else None


def _as_text(raw: bytes) -> str | None:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


@dataclass(frozen=True, slots=True)
class _Codec:
    name: str
    finder: re.Pattern[str]
    decode: Callable[[str], str | None]


#: Order matters only for reporting -- every codec whose candidate pattern matches is
#: tried. base64 before base64url so the commoner label wins on an overlapping run.
CODECS: tuple[_Codec, ...] = (
    _Codec("base64", _B64_RUN, _b64),
    _Codec("base64url", _B64URL_RUN, _b64url),
    _Codec("hex", _HEX_RUN, _hex),
    _Codec("percent", _PERCENT_RUN, _percent),
    _Codec("unicode_escape", _UNICODE_RUN, _unicode_escapes),
)


class EncodedScanner:
    """Decode candidate regions and re-run the real detectors on the result.

    ``inner_scan`` is the scanner to apply to decoded text -- normally
    ``scan_span_credentials``. Reusing it rather than reimplementing detection means
    every class the S0 pack knows about is covered here for free, and stays covered when
    the pack changes.
    """

    __slots__ = ("_inner", "_max_depth", "_enabled")

    def __init__(
        self,
        inner_scan: Callable[[Span], list[Finding]],
        *,
        max_depth: int = 2,
        enabled: bool = True,
    ) -> None:
        self._inner = inner_scan
        self._max_depth = max_depth
        self._enabled = enabled

    def __call__(self, span: Span) -> list[Finding]:
        if not self._enabled or len(span.text) < _MIN_RUN:
            return []
        return self._scan(span, span.text, depth=0)

    def _scan(self, span: Span, text: str, depth: int) -> list[Finding]:
        if depth >= self._max_depth:
            return []

        found: list[Finding] = []
        seen: set[tuple[int, int]] = set()
        budget = _MAX_CANDIDATES

        for codec in CODECS:
            for m in codec.finder.finditer(text):
                if budget <= 0:
                    log.debug("encoded-candidate budget exhausted on %s", span.path)
                    return found
                region = m.group(0)
                if len(region) > _MAX_REGION:
                    region = region[:_MAX_REGION]
                key = (m.start(), m.end())
                if key in seen:
                    continue

                decoded = codec.decode(region)
                if decoded is None or len(decoded) < _MIN_DECODED or not _printable(decoded):
                    continue
                budget -= 1
                seen.add(key)

                inner = self._inner(
                    Span(path=span.path, text=decoded, origin=span.origin, leg=span.leg)
                )
                if inner:
                    # The whole encoded run is the finding. Redacting a slice of base64
                    # leaves a blob that still decodes to most of the key.
                    found.extend(
                        self._lift(f, span, m.start(), m.end(), codec.name, depth)
                        for f in inner
                    )
                    continue

                # Nothing at this level -- try one more, for base64(json(...)) shapes.
                for nested in self._scan(span, decoded, depth + 1):
                    found.append(
                        self._lift(nested, span, m.start(), m.end(), codec.name, depth)
                    )
        return found

    @staticmethod
    def _lift(
        f: Finding, span: Span, start: int, end: int, codec: str, depth: int
    ) -> Finding:
        return Finding(
            span_path=span.path,
            start=start,
            end=end,
            entity_class=f.entity_class,
            confidence=f.confidence,
            tier=f.tier,
            leg=span.leg,
            # The codec chain is on the finding so the console can explain why this was
            # caught when the raw text contains nothing resembling a key. The S0 pack
            # identifies detectors by id rather than name, so fall back to the class --
            # a label reading "+base64" tells a reader nothing about what was found.
            detector_name=f"{f.detector_name or f.entity_class.value.lower()}+{codec}"
            + (f"@{depth + 1}" if depth else ""),
            advisory_only=f.advisory_only,
        )
