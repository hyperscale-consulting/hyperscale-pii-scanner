# pyright: reportPrivateUsage=false
import pytest

from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import scan
from hyperscale.pii_scanner._recognisers.postcode import UkPostcodeRecognizer
from tests.helpers import matches


@pytest.mark.parametrize(
    ("text", "expected", "score"),
    [
        ("lives at LS1 4AP today", "LS1 4AP", 0.6),
        ("lives at SW1A 1AA today", "SW1A 1AA", 0.6),
        ("lives at W1A 0AX today", "W1A 0AX", 0.6),
        ("lives at M1 1AE today", "M1 1AE", 0.6),
        ("lives at B33 8TH today", "B33 8TH", 0.6),
        ("lives at CR2 6XH today", "CR2 6XH", 0.6),
        ("lives at DN55 1PT today", "DN55 1PT", 0.6),
        ("lives at GIR 0AA today", "GIR 0AA", 0.6),
        ("lives at LS14AP today", "LS14AP", 0.45),
    ],
)
def test_full_postcode_positive(text: str, expected: str, score: float):
    assert (expected, score) in matches(UkPostcodeRecognizer(), text, "UK_POSTCODE")


@pytest.mark.parametrize(
    "text",
    [
        "lives at ls1 4ap today",  # postcodes are upper case
        "QV1 1AA",  # Q, V, X are not valid first letters
        "LS1 4CI",  # C, I, K, M, O, V not valid in the inward code
        "LS1 4APX",
        "ABC 123",
    ],
)
def test_full_postcode_negative(text: str):
    found = [
        t
        for t, score in matches(UkPostcodeRecognizer(), text, "UK_POSTCODE")
        if score >= 0.3
    ]
    assert found == []


def test_outward_code_has_low_score_without_context():
    found = matches(
        UkPostcodeRecognizer(), "The LS1 district was quiet.", "UK_POSTCODE"
    )
    assert found == [("LS1", 0.05)]


def test_outward_code_is_not_matched_inside_full_postcode():
    found = matches(UkPostcodeRecognizer(), "LS1 4AP", "UK_POSTCODE")
    assert found == [("LS1 4AP", 0.6)]


def test_outward_code_reported_only_with_context_via_scan():
    with_context = scan("Her postcode is LS1 and she is happy.")
    assert (HitKind.POSTCODE, "LS1") in {(h.kind, h.text) for h in with_context}
    without_context = scan("Vitamin B12 and form E1 were mentioned.")
    assert not any(h.kind == HitKind.POSTCODE for h in without_context)


def test_full_postcode_in_allowlist_is_not_reported():
    hits = scan("Office: LS1 4AP.", allowlist=["LS1 4AP"])
    assert hits == []
