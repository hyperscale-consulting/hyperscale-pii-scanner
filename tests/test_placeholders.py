import re

import pytest

from hyperscale.pii_scanner import placeholder_patterns_from_examples
from hyperscale.pii_scanner import scan


def _matches(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


def test_token_example_generalises_letter_and_digit_runs():
    (pattern,) = placeholder_patterns_from_examples(["MOTHER2FN"])
    assert _matches(pattern, "FATHER1SN")
    assert _matches(pattern, "CHILD12FN")
    assert not _matches(pattern, "mother2fn")
    assert not _matches(pattern, "MOTHER2")
    assert not _matches(pattern, "xMOTHER2FN")
    assert not _matches(pattern, "MOTHER2FNx")


def test_bracketed_example_keeps_punctuation_and_generalises_words():
    (pattern,) = placeholder_patterns_from_examples(["(LOCAL AUTHORITY)"])
    assert _matches(pattern, "(GP SURGERY)")
    assert _matches(pattern, "(FOSTER  CARER)")
    assert not _matches(pattern, "(local authority)")
    assert not _matches(pattern, "(SCHOOL1)")  # a different shape needs its own example
    assert not _matches(pattern, "LOCAL AUTHORITY")


def test_mixed_case_example_generalises_each_case_run():
    (pattern,) = placeholder_patterns_from_examples(["Child1"])
    assert _matches(pattern, "Mother2")
    assert not _matches(pattern, "CHILD1")


def test_duplicate_shapes_collapse_and_order_is_kept():
    patterns = placeholder_patterns_from_examples(
        ["MOTHER2FN", "(LOCAL AUTHORITY)", "FATHER1SN", "(SCHOOL1)"]
    )
    assert len(patterns) == 3
    assert _matches(patterns[0], "MOTHER2FN")
    assert _matches(patterns[1], "(LOCAL AUTHORITY)")
    assert _matches(patterns[2], "(SCHOOL1)")


@pytest.mark.parametrize("bad", ["", "   "])
def test_blank_example_is_rejected(bad: str):
    with pytest.raises(ValueError, match="example"):
        placeholder_patterns_from_examples([bad])


def test_single_string_is_rejected():
    with pytest.raises(TypeError, match="examples"):
        placeholder_patterns_from_examples("MOTHER2FN")  # type: ignore[arg-type]


def test_patterns_from_examples_suppress_placeholders_in_a_scan():
    patterns = placeholder_patterns_from_examples(["MOTHER2FN", "(LOCAL AUTHORITY)"])
    text = (
        "Ms MOTHER2SN lives with CHILD1FN, supported by (GP SURGERY) and "
        "(LOCAL AUTHORITY), in Harrogate."
    )
    hits = scan(text, placeholder_patterns=patterns)
    assert [(h.kind.value, h.text) for h in hits] == [("location", "Harrogate")]
