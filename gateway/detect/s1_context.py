"""S1 -- contextual detection. Config-driven. CODE-01 §6.2.

S0 asks *does this value look like a secret*. S1 asks *does the surrounding text say it
is one*. The second question is the only one that works on a value with no shape:

    DB_PASSWORD=hunter2          "hunter2" has no pattern and no entropy
    api_key: 7f3a9c              too short for the entropy floor to fire
    | service | token     |      a markdown column, typed by its header

This is what matters on RAG payloads. A retrieved config file, runbook or wiki page is
mostly key/value structure, and the key name is often the entire signal.

**Rules are data, in ``rules.yaml``, not branches here.** Three reasons, in order of how
much they matter: a tenant can extend the ruleset without a deploy; A4 can emit the same
shape at runtime; and a rule that turns out to be noisy can be retuned by editing one
number rather than by shipping code.

**The placeholder problem is the whole difficulty.** Documentation and config templates
are *made of* things that look like secrets -- ``password: <your-password>``,
``api_key: ${API_KEY}``, ``token: changeme``. A naive key-name rule flags every one, and
a RAG corpus of runbooks becomes unusable on the first document. ``value_guards`` in the
config is what stops that, and it is the part to tune first when false positives appear.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..contracts.entity_classes import EntityClass
from ..contracts.types import Finding, Tier
from ..spans.model import Span
from .baseline_rules import (
    BASELINE_KEY_RULES, BASELINE_MAX_LENGTH, BASELINE_MIN_LENGTH,
    BASELINE_MIN_VALUE_ENTROPY,
    BASELINE_TABLE_CONFIDENCE, BASELINE_TABLE_HEADER, RuleWeakened, compile_baseline,
)

log = logging.getLogger(__name__)


def _entropy(s: str) -> float:
    """Shannon entropy in bits per character."""
    from collections import Counter
    from math import log2

    n = len(s)
    if n < 2:
        return 0.0
    return -sum((c / n) * log2(c / n) for c in Counter(s).values())

DEFAULT_RULES = Path(__file__).with_name("rules.yaml")


@dataclass(frozen=True, slots=True)
class KeyRule:
    name: str
    entity_class: EntityClass
    pattern: re.Pattern[str]
    confidence: float


@dataclass(slots=True)
class ContextRules:
    """Compiled ruleset. Built once at load, never per request."""

    key_rules: list[KeyRule] = field(default_factory=list)
    structures: list[tuple[str, re.Pattern[str]]] = field(default_factory=list)
    ignore_values: list[re.Pattern[str]] = field(default_factory=list)
    min_length: int = 4
    max_length: int = 512
    min_value_entropy: float = 1.8
    tables_enabled: bool = True
    table_header: re.Pattern[str] | None = None
    table_confidence: float = 0.85
    table_max_rows: int = 500

    @classmethod
    def load(cls, path: Path | None = None) -> "ContextRules":
        """Baseline first, then config on top -- and config may only strengthen.

        The baseline is compiled into ``baseline_rules.py`` and is always present. A
        ruleset that lived only in an editable file could be silently emptied, and the
        result is a control that reports itself healthy while catching nothing. So the
        config layer can add rules, raise a confidence, or add placeholder patterns, and
        nothing else. Anything weaker raises :class:`RuleWeakened` by name.

        A missing or malformed config is fine -- the baseline still applies. A config
        that tries to *weaken* is not fine, and is the one case that stops the load.
        """
        keys, structs, ignores = compile_baseline()
        r = cls(key_rules=keys, structures=structs, ignore_values=ignores,
                min_length=BASELINE_MIN_LENGTH, max_length=BASELINE_MAX_LENGTH,
                min_value_entropy=BASELINE_MIN_VALUE_ENTROPY,
                table_header=re.compile(BASELINE_TABLE_HEADER),
                table_confidence=BASELINE_TABLE_CONFIDENCE)

        path = path or DEFAULT_RULES
        try:
            import yaml
            raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except FileNotFoundError:
            return r
        except Exception as exc:  # noqa: BLE001
            # Malformed config degrades to the baseline, which is still a working
            # ruleset. S0 and the baseline S1 are the floor of the product.
            log.error("rules.yaml unreadable (%s); using baseline only", exc)
            return r

        baseline_by_name = {b.name: b for b in BASELINE_KEY_RULES}
        seen: set[str] = set()

        for row in raw.get("key_names", []):
            name = row.get("name", "?")
            seen.add(name)
            try:
                conf = float(row["confidence"])
                base = baseline_by_name.get(name)
                if base is not None:
                    if conf < base.confidence:
                        raise RuleWeakened(
                            name, f"confidence {conf} below baseline {base.confidence}")
                    if row["pattern"] != base.pattern:
                        raise RuleWeakened(name, "pattern differs from baseline")
                    # Same rule, same or higher confidence -- replace the compiled one.
                    for i, k in enumerate(r.key_rules):
                        if k.name == name:
                            r.key_rules[i] = KeyRule(
                                name, EntityClass(row["entity_class"]),
                                re.compile(row["pattern"]), conf)
                            break
                    continue
                r.key_rules.append(KeyRule(
                    name, EntityClass(row["entity_class"]),
                    re.compile(row["pattern"]), conf))
            except RuleWeakened:
                raise
            except (KeyError, ValueError, re.error) as exc:
                log.error("S1 key rule %r rejected: %s", name, exc)

        missing = set(baseline_by_name) - seen
        if missing and raw.get("key_names"):
            # Deleting a baseline rule from the config is the quietest way to disable a
            # detector, so it is treated exactly like lowering its confidence to zero.
            raise RuleWeakened(sorted(missing)[0], "baseline rule absent from rules.yaml")

        for row in raw.get("structures", []):
            name = row.get("name", "?")
            if any(n == name for n, _ in r.structures):
                continue                                  # baseline already has it
            try:
                r.structures.append((name, re.compile(row["pattern"])))
            except (KeyError, re.error) as exc:
                log.error("S1 structure %r rejected: %s", name, exc)

        guards = raw.get("value_guards", {})
        # Only tightening is allowed: a higher floor and a lower ceiling narrow what
        # counts as a placeholder, which can only reduce misses.
        r.min_length = max(r.min_length, int(guards.get("min_length", r.min_length)))
        r.max_length = min(r.max_length, int(guards.get("max_length", r.max_length)))
        for pat in guards.get("ignore_values", []):
            try:
                r.ignore_values.append(re.compile(pat))   # additive: fewer false positives
            except re.error as exc:
                log.error("S1 ignore_values %r rejected: %s", pat, exc)

        t = raw.get("tables", {})
        r.tables_enabled = bool(t.get("enabled", True))
        r.table_confidence = max(r.table_confidence, float(t.get("confidence", 0)))
        r.table_max_rows = int(t.get("max_rows", r.table_max_rows))
        return r

    # ---- guards ----

    def is_placeholder(self, value: str) -> bool:
        """True for anything that is not plausibly a credential value.

        The main false-positive defence, and every guard here was earned by a real
        false positive rather than guessed at in advance.
        """
        v = value.strip().strip("\"'")
        if not (self.min_length <= len(v) <= self.max_length):
            return True

        # A credential has no internal whitespace. The env-assignment pattern captures
        # to end of line, so without this a log line reading `DB_PASSWORD=` followed by
        # formatted output becomes a finding with `12/34  100.0%` as its "value".
        if any(c.isspace() for c in v):
            return True

        # Repetition floor. `xx_xxxxxxxxxxxxxxxxxxx` measures 0.77 bits per character;
        # `hunter2`, a weak but real password, measures 2.81. Filler is not a secret.
        if _entropy(v) < self.min_value_entropy:
            return True

        return any(p.match(v) for p in self.ignore_values)

    def classify_key(self, key: str) -> KeyRule | None:
        """Highest-confidence rule matching this key name.

        The key is normalised so ``_`` and ``-`` act as word boundaries before matching.
        Without this, a word-boundary assertion silently fails on the most common real
        names there are: ``_`` is itself a word character, so a bounded ``secret`` does
        not match inside ``AWS_SECRET_KEY``, and a bounded ``pass`` does not match
        inside ``DB_PASSWORD``. The rules would look correct and catch almost nothing.

        Because the probe turns separators into spaces, rules must spell the separator
        class as ``[ _-]?`` and not ``[_-]?`` -- see ``rules.yaml``. Normalising here
        rather than complicating every pattern also keeps the rule syntax
        re2-compatible (no lookaround), which matters because A4 emits rules in this
        same shape at runtime.
        """
        probe = key.replace("_", " ").replace("-", " ")
        best: KeyRule | None = None
        for rule in self.key_rules:
            if rule.pattern.search(probe) and (best is None or rule.confidence > best.confidence):
                best = rule
        return best


class ContextScanner:
    """S1 as a span scanner. Composes with S0 rather than replacing it."""

    __slots__ = ("_rules",)

    def __init__(self, rules: ContextRules | None = None) -> None:
        self._rules = rules or ContextRules.load()

    def __call__(self, span: Span) -> list[Finding]:
        if not span.text or not self._rules.key_rules:
            return []
        out: list[Finding] = []
        out.extend(self._structured(span))
        if self._rules.tables_enabled:
            out.extend(self._tables(span))
        return out

    # -- key = value, key: value, --key value, Authorization: ... --
    def _structured(self, span: Span) -> list[Finding]:
        text, r = span.text, self._rules
        found: list[Finding] = []
        for struct_name, pattern in r.structures:
            for m in pattern.finditer(text):
                key, value = m.group("k"), m.group("v")
                rule = r.classify_key(key)
                if rule is None or r.is_placeholder(value):
                    continue
                # Offsets cover the VALUE only. Redacting the key as well would destroy
                # the structure of the document we are protecting.
                start = m.start("v")
                end = start + len(value.rstrip())
                found.append(Finding(
                    span_path=span.path, start=start, end=end,
                    entity_class=rule.entity_class, confidence=rule.confidence,
                    tier=Tier.CONTEXT, leg=span.leg,
                    detector_name=f"s1:{rule.name}:{struct_name}",
                ))
        return found

    # -- markdown / CSV columns typed by their header --
    def _tables(self, span: Span) -> list[Finding]:
        r = self._rules
        if r.table_header is None:
            return []
        lines = span.text.split("\n")
        if len(lines) < 2:
            return []

        found: list[Finding] = []
        offset = 0
        sensitive_cols: set[int] | None = None

        for i, line in enumerate(lines):
            if i > r.table_max_rows:
                break
            if "|" in line:
                cells = line.split("|")
                if sensitive_cols is None:
                    # First pipe row is the header. One check types the whole column.
                    sensitive_cols = {
                        j for j, c in enumerate(cells) if r.table_header.match(c)
                    }
                elif sensitive_cols:
                    pos = offset
                    for j, cell in enumerate(cells):
                        if j in sensitive_cols:
                            v = cell.strip()
                            if v and not r.is_placeholder(v) and set(v) != {"-"}:
                                s = pos + cell.index(v)
                                found.append(Finding(
                                    span_path=span.path, start=s, end=s + len(v),
                                    entity_class=EntityClass.GENERIC_SECRET,
                                    confidence=r.table_confidence,
                                    tier=Tier.CONTEXT, leg=span.leg,
                                    detector_name="s1:table_column",
                                ))
                        pos += len(cell) + 1
            offset += len(line) + 1
        return found
