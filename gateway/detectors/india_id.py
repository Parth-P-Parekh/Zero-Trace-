"""Indian government identifiers — the INDIA_ID family.

VOCAB-01 declared these classes and the government worked example writes rules about
them, but nothing produced them: a policy that says "mask Aadhaar" against a detector that
never emits `AADHAAR` is a rule that cannot fire. This closes that.

**Every detector here validates, it does not merely match.** These are short, dense,
digit-heavy strings that appear constantly in ordinary text — an order number, a phone
number with spaces, a git SHA prefix. A shape pattern alone would make the class useless
by crying wolf, and a class that cries wolf gets switched off, which is worse than not
having it. So:

    AADHAAR    12 digits, Verhoeff checksum, first digit 2-9
    GSTIN      15 chars, mod-36 checksum, embeds a valid PAN
    IFSC       11 chars, 5th character must be '0' (reserved by RBI)
    VOTER_ID   3 letters + 7 digits, with strict boundaries
    UPI_VPA    handle must be one a real PSP issues

`DL_NUMBER` is deliberately absent. Driving-licence formats vary by state and several
collapse to "two letters and some digits", which matches too much ordinary text to be
worth a class that would be ignored. Adding it needs per-state patterns, not a regex.
"""

from __future__ import annotations

from ..base.budget import Deadline
from ..base.detector import Detector, Match
from ..contracts.entity_classes import EntityClass
from ..contracts.types import Tier


# --------------------------------------------------------------------- Verhoeff --

#: Dihedral group D5 multiplication table. Verhoeff catches every single-digit error and
#: every adjacent transposition, which is why UIDAI chose it and why a bare 12-digit
#: pattern is not an acceptable substitute.
_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6), (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8), (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2), (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4), (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2), (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0), (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5), (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


def verhoeff_ok(digits: str) -> bool:
    check = 0
    for i, ch in enumerate(reversed(digits)):
        check = _D[check][_P[i % 8][int(ch)]]
    return check == 0


class AadhaarDetector(Detector):
    """A 12-digit Aadhaar, spaced or not.

    Written as `2234 5678 9012` far more often than as a bare run, so the pattern allows
    the separators and `confirm` strips them before checking. Matching only the compact
    form would miss the way people actually paste it.
    """

    name = "aadhaar"
    entity_class = EntityClass.AADHAAR
    tier = Tier.DETERMINISTIC
    candidate_pattern = r"[2-9][0-9]{3}[ -]?[0-9]{4}[ -]?[0-9]{4}"

    def confirm(self, text: str, start: int, end: int, deadline: Deadline) -> Match | None:
        digits = "".join(c for c in text[start:end] if c.isdigit())
        if len(digits) != 12:
            return None
        # UIDAI never issues a number beginning 0 or 1, which removes a large class of
        # ordinary 12-digit runs before the checksum is even reached.
        if digits[0] in "01":
            return None
        if not verhoeff_ok(digits):
            return None
        if _touching_alnum(text, start, end):
            return None
        return Match(start=start, end=end, confidence=0.97)


# ------------------------------------------------------------------------ GSTIN --

_GST_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_PAN_HOLDER_TYPES = frozenset("ABCFGHLJPTK")


def gstin_ok(value: str) -> bool:
    """Mod-36 with alternating weights, the checksum the GST portal uses."""
    if len(value) != 15:
        return False
    total = 0
    for i, ch in enumerate(value[:14]):
        pos = _GST_CHARS.find(ch)
        if pos < 0:
            return False
        product = pos * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return _GST_CHARS[(36 - total % 36) % 36] == value[14]


class GSTINDetector(Detector):
    """A GST identification number: state code + PAN + entity + 'Z' + checksum."""

    name = "gstin"
    entity_class = EntityClass.GSTIN
    tier = Tier.DETERMINISTIC
    candidate_pattern = r"[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]"

    def confirm(self, text: str, start: int, end: int, deadline: Deadline) -> Match | None:
        value = text[start:end]
        # A GSTIN embeds a PAN at characters 2-11, so the holder-type rule applies here
        # too -- it is the 4th character of that PAN, which is index 5 of the GSTIN.
        if value[5] not in _PAN_HOLDER_TYPES:
            return None
        if not gstin_ok(value):
            return None
        if _touching_alnum(text, start, end):
            return None
        return Match(start=start, end=end, confidence=0.97)


# ------------------------------------------------------------------------- IFSC --

class IFSCDetector(Detector):
    """A bank branch code. Eleven characters, and the fifth is always '0'.

    That reserved zero is what makes an anchorless eleven-character token safe to claim:
    it is RBI-mandated, so an arbitrary alphanumeric run almost never satisfies it.
    """

    name = "ifsc"
    entity_class = EntityClass.IFSC
    tier = Tier.DETERMINISTIC
    candidate_pattern = r"[A-Z]{4}0[0-9A-Z]{6}"

    def confirm(self, text: str, start: int, end: int, deadline: Deadline) -> Match | None:
        if _touching_alnum(text, start, end):
            return None
        # An all-zero or all-same branch code is a placeholder in test fixtures far more
        # often than a real branch.
        if len(set(text[start + 5 : end])) == 1:
            return None
        return Match(start=start, end=end, confidence=0.9)


# --------------------------------------------------------------------- VOTER_ID --

class VoterIDDetector(Detector):
    """An EPIC number: three letters then seven digits.

    The weakest shape in this file -- there is no checksum -- so it leans entirely on
    boundaries and carries a lower confidence. It will not enforce alone under the
    default threshold, which is the right outcome for a pattern this thin.
    """

    name = "voter_id"
    entity_class = EntityClass.VOTER_ID
    tier = Tier.DETERMINISTIC
    candidate_pattern = r"[A-Z]{3}[0-9]{7}"

    def confirm(self, text: str, start: int, end: int, deadline: Deadline) -> Match | None:
        if _touching_alnum(text, start, end):
            return None
        return Match(start=start, end=end, confidence=0.72)


# ---------------------------------------------------------------------- UPI_VPA --

#: Handles real payment service providers issue. An open `anything@anything` pattern would
#: match every email address in every payload, so the list is the detector.
_UPI_HANDLES = (
    "@oksbi", "@okhdfcbank", "@okicici", "@okaxis", "@ybl", "@paytm", "@apl",
    "@upi", "@ibl", "@axl", "@airtel", "@jupiteraxis", "@fbl", "@idfcbank",
)


class UPIVPADetector(Detector):
    """A UPI virtual payment address, anchored on the PSP handle."""

    name = "upi_vpa"
    entity_class = EntityClass.UPI_VPA
    tier = Tier.DETERMINISTIC
    anchors = _UPI_HANDLES
    max_span = 64

    def confirm(self, text: str, start: int, end: int, deadline: Deadline) -> Match | None:
        # Walk back over the local part. A handle with nothing in front of it is prose
        # about UPI, not an address.
        i = start
        while i > 0 and (text[i - 1].isalnum() or text[i - 1] in "._-"):
            i -= 1
        if start - i < 3:
            return None
        if end < len(text) and (text[end].isalnum() or text[end] in "._-"):
            return None
        return Match(start=i, end=end, confidence=0.93)


def _touching_alnum(text: str, start: int, end: int) -> bool:
    """True when the match sits inside a longer token.

    A PAN-shaped run in the middle of a build id is a build id. Every detector here needs
    this, so it lives once.
    """
    if start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
        return True
    return end < len(text) and (text[end].isalnum() or text[end] == "_")


INDIA_ID_DETECTORS = (
    AadhaarDetector(),
    GSTINDetector(),
    IFSCDetector(),
    VoterIDDetector(),
    UPIVPADetector(),
)
