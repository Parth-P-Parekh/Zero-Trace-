"""Co-occurrence: when the set identifies someone, even if no single value does.

An Aadhaar is twelve digits with a Verhoeff check digit, and **one in ten random
twelve-digit strings passes it** -- measured, not assumed. So the checksum removes 90% of
order numbers and keeps the rest: a filter, not a decision. Blocking on it alone floods a
payload full of invoice numbers; waiting for checksum-plus-label misses the number typed
without one.

A bare identifier is ambiguous. A *record* is not. That is what this scans for, and it is
why it reaches citizens the organisation has never seen -- unlike matching against a list
of the ones it already has.

**Most of this file is false positives**, because the failure that matters is a payload of
order numbers and log lines being masked until someone turns the class off.
"""

from __future__ import annotations

import pytest

from gateway.detect.composite import QUORUM, WINDOW, signals_in
from hooks.zt_check import check_embedded


def _n() -> str:
    """A twelve-digit run. Assembled so this file is not itself a record."""
    return "4829" + " " + "1057" + " " + "3364"


def _join(*parts: str) -> str:
    return "".join(parts)


def _blocked(text: str) -> bool:
    return not check_embedded(text, "test")["allow"]


def _classes(text: str) -> list[str]:
    return check_embedded(text, "test").get("classes") or []


# --------------------------------------------------------- the checksum's limit --

def test_the_checksum_keeps_one_in_ten_random_numbers():
    """The measurement the whole design rests on. If this drifts, revisit the design."""
    import random

    from gateway.detectors.india_id import verhoeff_ok

    random.seed(11)
    trials = 20_000
    passed = sum(
        1 for _ in range(trials)
        if verhoeff_ok("".join(random.choice("0123456789") for _ in range(12)))
    )
    assert 0.07 < passed / trials < 0.13, (
        f"{passed / trials:.1%} of random 12-digit strings pass Verhoeff -- the "
        f"checksum is a filter, not a decision, and the composite scanner exists "
        f"because of it"
    )


# ------------------------------------------------------------- true positives --

def test_a_record_is_caught_even_when_the_number_is_not_a_valid_aadhaar():
    """The case the user reported: an identifier nobody labelled, inside a record."""
    text = (_join("app", "licant na", "me") + ": R Sharma, " + _join("d", "ob")
            + " 12/04/1988, " + _join("dis", "trict") + " Pune, " + _n())
    assert _blocked(text)
    assert "QUASI_IDENTIFIER_SET" in _classes(text)


def test_a_json_record_is_caught():
    """A JSON key is `"name":` -- the quote sits between the word and the colon, and
    missing that scores zero on most of what a retriever returns."""
    text = ('{"' + _join("u", "id") + '": "' + _n().replace(" ", "")
            + '", "' + _join("na", "me") + '": "R Sharma"}')
    assert _blocked(text)


def test_a_kyc_form_is_caught():
    text = (_join("Na", "me") + ": A Kumar  " + _join("S", "/o") + " B Kumar  "
            + _join("D", "OB") + ": 03/07/1990  " + _n())
    assert _blocked(text)


# ------------------------------------------------------------ false positives --

def test_a_bare_twelve_digit_number_is_not_a_record():
    assert not _blocked("reference " + _n() + " for the shipment")


def test_a_page_of_order_numbers_is_not_a_record():
    assert not _blocked("orders 100000000001 100000000002 100000000003 shipped tuesday")


def test_an_invoice_with_a_date_is_not_a_record():
    """One signal is a coincidence in any large payload; the quorum is what stops it."""
    assert not _blocked("invoice " + _n().replace(" ", "") + " dated 12/04/2024")


def test_a_log_line_with_a_unix_uid_is_not_a_record():
    """`uid=1000` is a user id. It must not label a number elsewhere in the document."""
    assert not _blocked("2024-04-12 " + _join("u", "id") + "=1000 pid="
                        + _n().replace(" ", "") + " restarting service")


def test_engineering_chat_is_untouched():
    for text in ("commit 9f2c1ab8e4d5 and bump timeout 100000000001 ms in the loop",
                 "refactor the retry loop so it backs off exponentially",
                 "the CI job failed on windows-latest after 100000000001 ns"):
        assert not _blocked(text), text


def test_a_name_alone_beside_a_number_is_not_enough():
    """Below quorum on purpose: one signal and a number is most of the internet."""
    assert not _blocked("R Sharma " + _n())


# ------------------------------------------------------------------- windowing --

def test_signals_must_be_near_the_number():
    """Scoring the whole span was the first attempt and it was too loose.

    Any large document contains a date somewhere and the word "name" somewhere, so a page
    of order numbers reached quorum on signals that had nothing to do with the numbers. A
    record is a *local* structure.
    """
    far = _join("na", "me") + ": R Sharma" + (" filler" * 80) + " ref " + _n()
    assert not _blocked(far)
    assert signals_in(far) == ()


def test_the_window_is_a_couple_of_lines_not_a_document():
    assert 60 <= WINDOW <= 400
    assert QUORUM >= 2


# ---------------------------------------------------------------- the finding --

def test_the_finding_carries_no_value():
    from gateway.detect.composite import scan_span_composite
    from gateway.spans.model import Span

    text = (_join("app", "licant na", "me") + ": R Sharma, " + _join("d", "ob")
            + " 12/04/1988, " + _n())
    span = Span(path="prompt", text=text, origin="user", leg="outbound",
                byte_start=0, byte_end=len(text.encode()))
    for finding in scan_span_composite(span):
        assert _n() not in str(vars(finding) if hasattr(finding, "__dict__") else finding)


def test_signals_are_named_never_quoted():
    """Diagnostics name the kind of corroboration, never the matched text."""
    text = (_join("app", "licant na", "me") + ": R Sharma, " + _join("d", "ob")
            + " 12/04/1988, " + _n())
    assert "R Sharma" not in str(signals_in(text))
    assert "name" in signals_in(text)
