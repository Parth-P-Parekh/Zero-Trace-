"""Part A and the root share one entity vocabulary.

Agenda Task 2. Part A shipped its own copy of VOCAB-01 as a declared mirror, and the two
were byte-identical when compared — but a mirror is only correct until someone edits one
side. A class added to the root and not to Part A would not fail: the Finding would simply
be rejected as unknown, at runtime, in the control plane, for a class the detector was
built to find. That is a silent hole rather than a loud one, which is why the mirror is
deleted rather than tested for equality.

These tests fail if the two ever come apart again.
"""

from __future__ import annotations

import pytest

from gateway.contracts.entity_classes import CLASS_TO_FAMILY, EntityClass


def _finding(entity_class: str):
    from zerotrace.spans.model import Finding

    return Finding(entity_class=entity_class, span_path="messages[0].content",
                   leg="outbound")


def test_every_root_class_constructs_a_part_a_finding():
    """The direction that matters: a class we can detect must be one they can record."""
    for cls in EntityClass:
        assert _finding(cls.value).entity_class == cls.value


def test_families_agree_for_every_class():
    for cls in EntityClass:
        expected = CLASS_TO_FAMILY[cls]
        assert _finding(cls.value).family == getattr(expected, "value", expected)


def test_part_a_has_no_class_the_root_does_not():
    """A Part A-only class would be undetectable, so it must not exist."""
    from zerotrace.spans import model

    assert set(model.ENTITY_CLASSES) == {c.value for c in EntityClass}


def test_an_unknown_class_is_still_refused():
    with pytest.raises(ValueError, match="not in the closed"):
        _finding("NOT_A_REAL_CLASS")


def test_retired_names_are_not_quietly_accepted():
    """API_KEY and MEDICAL predate VOCAB-01. Aliasing them would let stale rules match."""
    for retired in ("API_KEY", "MEDICAL", "PII"):
        with pytest.raises(ValueError):
            _finding(retired)


def test_the_duplicate_vocabulary_module_is_gone():
    """Deleted, not just unused: an importable copy invites a future edit."""
    import importlib.util

    assert importlib.util.find_spec("zerotrace.spans.vocab") is None
