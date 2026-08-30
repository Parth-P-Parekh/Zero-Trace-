"""Deciding what Loop 2 gets to look at.

There are two kinds of uncertainty and the code only ever handled one of them.

**The amber finding.** A detector fired at 0.35–0.75: something looked like a PAN and the
checksum was borderline, or a context scanner matched a key name without a shape to back
it. This was already escalated, from two places in `app.py`, with the condition written
out twice.

**The unclaimed span** — and this is the one that was missing. `BR-2291-KOL-77213` under a
key called `beneficiary_ref` produces *no finding at all*, because no detector in the pack
knows what a beneficiary reference looks like. `matching` is empty, the amber test is
`matching and any(...)`, and so the span that Loop 2 exists to learn from was the one span
guaranteed never to reach it. `learned.py` opens by describing the loop as running on "a
span nobody claimed"; until this module, nothing ever sent it one.

That gap mattered more than it looks. The classes with no hand-written detector —
`PERSON`, `ADDRESS`, `CUSTOMER_DATA` and their neighbours — are *deliberately* undetectable
by regex, because what a customer identifier looks like is a fact about one organisation's
schema. They can only ever be learned. So the loop that learns them was cut off from its
entire input.

**Volume is the whole difficulty.** Every prose span is also unclaimed. Escalating them all
would flood the queue, cost a model call each, and teach the pack nothing — so a span has
to look like an *identifier* before it is worth a question. The filter below is
deliberately narrow and deliberately cheap, and it errs towards missing things: a missed
escalation costs one learning opportunity, while a flood costs the queue its meaning.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from .features import EscalationFeatures, charset_class, features_of

log = logging.getLogger(__name__)

#: The amber band: a detector fired but not with enough confidence to enforce.
BAND_LO = 0.35
BAND_HI = 0.75

#: An unclaimed span has to be at least this long to be an identifier, and at most this
#: long to be anything but prose. `AB-1` is noise; a 200-character run is a sentence.
MIN_LEN = 6
MAX_LEN = 128

#: How many spans one request may escalate. A payload with two hundred unclaimed
#: identifier-shaped fields is a bulk export, and the tenth one teaches nothing the first
#: one did not -- while the model call for each is real money and a real queue slot.
MAX_PER_REQUEST = 8

#: Alphabets an identifier plausibly uses. `mixed` and `devanagari` are excluded because
#: at this length they are overwhelmingly names and free text, which the loop must not be
#: asked to classify -- that is the `PERSON` problem and it needs a model on the *record*,
#: not a synthesised regex on the value.
IDENTIFIER_CHARSETS = frozenset({"digits", "hex", "base64ish", "ascii"})


def enabled() -> bool:
    """Is Loop 2 switched on for this process?

    Two ways to say no, because the two callers are different. `ZT_LOOP2=off` covers a
    single run or a CI job; a `loop2-off` marker under `ZT_HOME` covers the machine, and
    is what `zerotrace loop2 off` writes -- the hook is a fresh process on every prompt,
    so an environment variable exported in one shell would not reach it.

    Default is on. An improvement loop that has to be discovered and enabled is one that
    never runs anywhere, which is most of how this one spent its life already.
    """
    flag = os.environ.get("ZT_LOOP2", "").strip().lower()
    if flag in ("0", "off", "false", "no"):
        return False
    if flag in ("1", "on", "true", "yes"):
        return True
    home = Path(os.environ.get("ZT_HOME") or (Path.home() / ".zerotrace"))
    return not (home / "loop2-off").exists()


def is_identifier_shaped(text: str) -> bool:
    """Could this span be an identifier nobody has a detector for?

    Four cheap tests, in the order that rejects fastest. The rule that does most of the
    work is "no internal whitespace": an identifier is one token. That single condition
    removes essentially all prose, which is what makes escalating unclaimed spans
    affordable at all.
    """
    text = text.strip()
    if not (MIN_LEN <= len(text) <= MAX_LEN):
        return False
    if any(c.isspace() for c in text):
        return False
    if charset_class(text) not in IDENTIFIER_CHARSETS:
        return False
    # A digit somewhere. A pure-alphabetic token of this length is a word, a class name
    # or a path component far more often than it is a reference number, and the ones
    # that are not will be caught the moment they appear beside a digit-bearing sibling.
    return any(c.isdigit() for c in text)


#: Characters that separate tokens inside a prose span. Not `str.split()`: an identifier
#: is routinely followed by a comma or wrapped in quotes, and splitting on whitespace
#: alone leaves `BR-2291-KOL-77213,` with a trailing comma that changes its shape.
_TOKEN_SPLIT = re.compile(r"""[\s,;()\[\]{}<>"'`]+""")

#: Trailing punctuation to shed once a token is isolated. A sentence-final full stop is
#: not part of the reference number.
_TRIM = ".:!?-_/"


def tokens_in(text: str) -> list[str]:
    """Identifier-shaped tokens inside a prose span.

    A span is a whole field value, so in a structured payload the span *is* the
    identifier -- but in a typed prompt it is a sentence, and the interesting thing is
    one word inside it. The first version of this filter tested the span text as a whole
    and therefore escalated nothing at all from ordinary prompts, which is most of what
    a coding agent sees.
    """
    out: list[str] = []
    for raw in _TOKEN_SPLIT.split(text):
        token = raw.strip(_TRIM)
        if token and is_identifier_shaped(token):
            out.append(token)
    return out


def spans_to_escalate(tree: Any, check: Any) -> list[tuple[Any, tuple]]:
    """Every span in this request worth a question, with the findings that touch it.

    Returns `(span, matching_findings)` pairs. An amber span carries its findings; an
    unclaimed span carries an empty tuple, and that emptiness is itself the signal --
    `detectors_near_miss` and `detectors_fired` both being empty is what tells the
    adjudicator "nothing in the pack has an opinion about this".
    """
    out: list[tuple[Any, tuple]] = []
    for span in tree:
        matching = tuple(f for f in check.findings if f.span_path == span.path)
        if matching:
            # Claimed. Only interesting while the pack is unsure about it.
            if any(BAND_LO <= f.confidence < BAND_HI for f in matching):
                out.append((span, matching))
            continue
        # Unclaimed. The span itself may be the identifier (a structured payload), or
        # it may be a sentence with one inside it (a typed prompt).
        if is_identifier_shaped(span.text):
            out.append((span, ()))
        else:
            for token in tokens_in(span.text)[:MAX_PER_REQUEST]:
                # Same path, same origin, same leg -- the *token* is what gets shaped.
                # Keeping the path means the safe-path hash still points at the field
                # the identifier was found in, which is what makes a proposed rule
                # applicable next time.
                out.append((replace(span, text=token), ()))
        if len(out) >= MAX_PER_REQUEST:
            break
    return out[:MAX_PER_REQUEST]


def escalate(intel: Any, tree: Any, check: Any, tenant_key: bytes,
             neighbours_of: Any = None) -> int:
    """Enqueue every worthwhile span. Returns how many. Never raises, never awaits.

    The caller is on the request path, so this must be incapable of failing it. Loop 2 is
    an improvement loop: losing an escalation costs a future detector, never this
    response.
    """
    if not enabled():
        return 0
    count = 0
    try:
        for span, matching in spans_to_escalate(tree, check):
            neighbours = ()
            if neighbours_of is not None:
                try:
                    neighbours = neighbours_of(check, span)
                except Exception:  # noqa: BLE001
                    neighbours = ()
            intel.maybe_escalate(
                features_of(span, matching, tenant_key, neighbours=neighbours)
            )
            count += 1
    except Exception:  # noqa: BLE001
        log.warning("escalation skipped for this request", exc_info=True)
    return count


def unclaimed(features: EscalationFeatures) -> bool:
    """True when no detector had any opinion about this span.

    The adjudicator is told this explicitly rather than left to infer it from two empty
    tuples, because "nothing fired" and "something nearly fired" are different questions
    and the prompt should not have to guess which one it is being asked.
    """
    return not features.detectors_fired and not features.detectors_near_miss
