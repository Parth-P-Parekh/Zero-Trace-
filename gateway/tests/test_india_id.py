"""The INDIA_ID detectors.

VOCAB-01 declared these classes and the government policy writes rules about them, but
nothing produced them -- a rule that says "mask Aadhaar" against a detector that never
emits `AADHAAR` cannot fire. These are the detectors that close that.

**Most of this file is false positives.** These are short, digit-dense strings that look
like things which appear in every payload: order numbers, phone numbers, git SHAs, build
identifiers, email addresses. A detector that cries wolf gets switched off, and a class
that is switched off is worse than one that was never added. So each true positive here is
paired with the ordinary text it must not claim.

Fixtures are computed, not hardcoded: the check digit is derived so the test cannot drift
from the checksum it is meant to exercise.
"""

from __future__ import annotations

import pytest

from gateway.detectors.india_id import gstin_ok, verhoeff_ok
from hooks.zt_check import check_embedded

_GST_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def aadhaar(prefix: str = "23456789012") -> str:
    return next(prefix + d for d in "0123456789" if verhoeff_ok(prefix + d))


def gstin() -> str:
    base = "27" + "ABC" + "PZ" + "1234" + "C" + "1" + "Z"
    return next(base + c for c in _GST_CHARS if gstin_ok(base + c))


def ifsc() -> str:
    return "HDFC" + "0" + "001234"


def upi() -> str:
    return "ramesh.kumar" + "@" + "oksbi"


def _classes(text: str) -> list[str]:
    return check_embedded(text, "test").get("classes") or []


def _blocked(text: str) -> bool:
    return not check_embedded(text, "test")["allow"]


# ----------------------------------------------------------------- checksums --

def test_verhoeff_accepts_a_valid_number_and_rejects_a_transposition():
    number = aadhaar()
    assert verhoeff_ok(number)
    # Verhoeff's whole point: adjacent transpositions are caught, unlike a mod-10 sum.
    swapped = number[:4] + number[5] + number[4] + number[6:]
    assert not verhoeff_ok(swapped)


def test_verhoeff_rejects_a_single_digit_error():
    number = aadhaar()
    for i in range(12):
        wrong = "0" if number[i] != "0" else "1"
        assert not verhoeff_ok(number[:i] + wrong + number[i + 1 :])


def test_gstin_checksum_rejects_a_wrong_check_character():
    value = gstin()
    assert gstin_ok(value)
    other = next(c for c in _GST_CHARS if c != value[14])
    assert not gstin_ok(value[:14] + other)


# --------------------------------------------------------------- true positives --

def test_aadhaar_is_found_compact_and_spaced():
    number = aadhaar()
    spaced = f"{number[:4]} {number[4:8]} {number[8:]}"
    assert "AADHAAR" in _classes(number)
    assert "AADHAAR" in _classes(spaced)
    assert "AADHAAR" in _classes(f"citizen aadhaar is {spaced}, please verify")


def test_aadhaar_is_found_with_hyphens():
    number = aadhaar()
    assert "AADHAAR" in _classes(f"{number[:4]}-{number[4:8]}-{number[8:]}")


def test_gstin_is_found():
    assert "GSTIN" in _classes(f"our gstin is {gstin()}")


def test_ifsc_is_found():
    assert "IFSC" in _classes(f"transfer to {ifsc()} account")


def test_upi_vpa_is_found():
    assert "UPI_VPA" in _classes(f"pay me at {upi()} today")


# -------------------------------------------------------------- false positives --

def test_a_twelve_digit_order_number_is_not_an_aadhaar():
    """The single most common way this class would embarrass itself."""
    assert not _blocked("order 100000000001 shipped on tuesday")


def test_a_failed_checksum_is_not_an_aadhaar():
    """A shape match alone is not a decision."""
    assert "AADHAAR" not in _classes("2345 6789 0123")


def test_a_number_starting_zero_or_one_is_not_an_aadhaar():
    """UIDAI never issues these, so the range check runs before the checksum."""
    for prefix in ("0", "1"):
        candidate = prefix + aadhaar()[1:]
        assert "AADHAAR" not in _classes(candidate)


def test_a_timestamp_is_not_an_aadhaar():
    assert not _blocked("epoch millis 1788054122000 recorded")


def test_an_email_address_is_not_a_upi_vpa():
    """An open `anything@anything` pattern would claim every address in every payload."""
    assert "UPI_VPA" not in _classes("mail me at ramesh.kumar" + "@" + "gmail.com")


def test_a_bare_handle_with_nothing_in_front_is_not_a_vpa():
    assert "UPI_VPA" not in _classes("we support " + "@" + "oksbi payments")


def test_a_git_sha_is_not_an_indian_identifier():
    assert not _blocked("commit 9f2c1ab8e4d5c6b7a8091f2e3d4c5b6a7f8e9d0c")


def test_ordinary_engineering_text_is_clean():
    for text in ("refactor the retry loop with exponential backoff",
                 "bump httpx from 0.27.0 to 0.28.1",
                 "the CI job failed on windows-latest with exit code 1"):
        assert not _blocked(text), text


def test_a_placeholder_branch_code_is_not_an_ifsc():
    """`ABCD0000000` is a fixture, not a branch."""
    assert "IFSC" not in _classes("use ABCD" + "0" + "000000 for testing")


def test_an_identifier_embedded_in_a_longer_token_is_not_claimed():
    """A PAN-shaped run inside a build id is a build id."""
    number = aadhaar()
    assert "AADHAAR" not in _classes(f"build_{number}_rc1")


# ------------------------------------------------------------------ confidence --

def test_voter_id_does_not_enforce_on_its_own():
    """Three letters and seven digits, with no checksum, is too thin to block on.

    It is still emitted -- it corroborates, and Loop 2 can see it -- but the confidence
    sits below the enforcement threshold on purpose.
    """
    assert not _blocked("epic ABC" + "1234567" + " issued")


@pytest.mark.parametrize("cls", ["AADHAAR", "GSTIN", "IFSC", "UPI_VPA", "VOTER_ID"])
def test_every_class_is_in_the_closed_vocabulary(cls):
    from gateway.contracts.entity_classes import EntityClass

    assert EntityClass(cls)


def test_the_registry_is_the_single_source_of_detectors():
    """Five call sites used to build their own list; five lists is five answers."""
    from gateway.detectors import ALL_DETECTORS
    from gateway.detectors.india_id import INDIA_ID_DETECTORS

    names = {d.name for d in ALL_DETECTORS}
    assert {d.name for d in INDIA_ID_DETECTORS} <= names


# --------------------------------------------------- labelled, but not valid --

def test_a_labelled_aadhaar_is_caught_even_when_the_checksum_fails():
    """"my aadhaar is 1234 5678 9012" is a disclosure whatever the digits do.

    A control that waves it through because the checksum fails is technically right and
    practically useless -- it would also miss a real Aadhaar mistyped by one digit, which
    is the likeliest way a genuine one gets pasted.
    """
    assert "AADHAAR" in _classes("my aadhaar is 1234 5678 9012")
    assert "AADHAAR" in _classes("aadhar number 9876 5432 1098 please verify")
    assert "AADHAAR" in _classes("UIDAI ref 9876 5432 1098")


def test_the_label_may_be_in_hindi():
    assert "AADHAAR" in _classes("मेरा आधार 9876 5432 1098 है")


def test_an_unlabelled_invalid_number_is_still_not_an_aadhaar():
    """The label is the evidence in that path. Without it, the checksum is."""
    assert "AADHAAR" not in _classes("reference 1234 5678 9012 for the shipment")


def test_a_distant_mention_does_not_label_a_number():
    """"aadhaar" in a heading two paragraphs up says nothing about this number."""
    text = "aadhaar verification service\n" + "\n".join("filler line" for _ in range(6))
    text += "\ninvoice total 1234 5678 9012"
    assert "AADHAAR" not in _classes(text)


def test_overlapping_detectors_do_not_shadow_each_other():
    """The bug this merge fixed, kept as a regression.

    Two detectors matching the same span meant the stricter pattern won the candidate,
    its confirm() rejected the checksum, and the second never saw the span --
    `1234 5678 9012` was caught and `9876 5432 1098` was not, for no reason a user could
    have guessed.
    """
    for number in ("1234 5678 9012", "9876 5432 1098", "2234 5678 9012"):
        assert "AADHAAR" in _classes(f"my aadhaar is {number}"), number
