# pyright: reportPrivateUsage=false
import pytest

from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import scan
from hyperscale.pii_scanner._recognisers.case_reference import CaseReferenceRecognizer
from tests.helpers import matches


@pytest.mark.parametrize(
    ("text", "expected", "score"),
    [
        ("Case ZC24C50123 concerns", "ZC24C50123", 0.7),
        ("Case FD24P00123 concerns", "FD24P00123", 0.7),
        ("see [2026] EWFC 12 at", "[2026] EWFC 12", 0.85),
        ("see [2024] EWHC 123 (Fam) at", "[2024] EWHC 123 (Fam)", 0.85),
        ("see [2023] EWCA Civ 45 at", "[2023] EWCA Civ 45", 0.85),
        ("see [2022] UKSC 1 at", "[2022] UKSC 1", 0.85),
        ("see [2026] EWFC 12 (B) at", "[2026] EWFC 12 (B)", 0.85),
        ("see [2021] EWCOP 7 at", "[2021] EWCOP 7", 0.85),
    ],
)
def test_case_reference_positive(text: str, expected: str, score: float):
    assert (expected, score) in matches(
        CaseReferenceRecognizer(), text, "CASE_REFERENCE"
    )


@pytest.mark.parametrize(
    "text",
    [
        "zc24c50123",  # case numbers are upper case
        "AB123456C",  # that is a NINO shape
        "[2026] 12",
        "[2026] XYZ 12",
        "ZC24C5012",
    ],
)
def test_case_reference_negative(text: str):
    found = [
        t
        for t, score in matches(CaseReferenceRecognizer(), text, "CASE_REFERENCE")
        if score >= 0.3
    ]
    assert found == []


def test_crown_court_and_cps_numbers_need_context():
    found = matches(
        CaseReferenceRecognizer(), "T20247123 and 01AB1234567", "CASE_REFERENCE"
    )
    assert found == [("01AB1234567", 0.2), ("T20247123", 0.2)]
    hits = scan("Crown Court case T20247123 was listed. The URN 01AB1234567 applies.")
    assert {(h.kind, h.text) for h in hits} >= {
        (HitKind.CASE_REFERENCE, "T20247123"),
        (HitKind.CASE_REFERENCE, "01AB1234567"),
    }
    plain = scan("Serial T20247123 was printed.")
    assert not any(h.kind == HitKind.CASE_REFERENCE for h in plain)
