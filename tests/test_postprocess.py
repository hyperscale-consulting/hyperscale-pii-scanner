# pyright: reportPrivateUsage=false
import re

import pytest
from presidio_analyzer import RecognizerResult

from hyperscale.pii_scanner import Hit
from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner._postprocess import build_hits
from hyperscale.pii_scanner._postprocess import Candidate
from hyperscale.pii_scanner._postprocess import resolve_overlaps
from hyperscale.pii_scanner._postprocess import suppress
from hyperscale.pii_scanner._postprocess import suppression_spans
from hyperscale.pii_scanner._postprocess import to_candidates


def _result(
    entity: str, start: int, end: int, score: float, name: str = "R"
) -> RecognizerResult:
    return RecognizerResult(
        entity_type=entity,
        start=start,
        end=end,
        score=score,
        recognition_metadata={RecognizerResult.RECOGNIZER_NAME_KEY: name},
    )


def _cand(
    kind: HitKind, start: int, end: int, score: float = 0.5, name: str = "R"
) -> Candidate:
    return Candidate(kind=kind, start=start, end=end, score=score, recogniser=name)


def test_to_candidates_maps_entities_and_drops_unknown_and_low_scores():
    results = [
        _result("PERSON", 0, 4, 0.85, "SpacyRecognizer"),
        _result("UK_NHS", 5, 15, 1.0, "NhsRecognizer"),
        _result("CREDIT_CARD", 16, 20, 0.9),
        _result("PERSON", 21, 25, 0.2),
    ]
    cands = to_candidates(results)
    assert cands == [
        Candidate(HitKind.PERSON, 0, 4, 0.85, "SpacyRecognizer"),
        Candidate(HitKind.NHS_NUMBER, 5, 15, 1.0, "NhsRecognizer"),
    ]


def test_structured_kind_beats_model_kind_on_overlap():
    cands = [
        _cand(HitKind.ORGANISATION, 0, 12, 0.85),  # "Postcode HG1"
        _cand(HitKind.POSTCODE, 9, 16, 0.6),  # "HG1 1AA"
    ]
    assert resolve_overlaps(cands) == [cands[1]]


def test_structured_priority_order():
    dob = _cand(HitKind.DATE_OF_BIRTH, 5, 15, 0.9)
    date = _cand(HitKind.DATE, 5, 15, 0.6)
    phone = _cand(HitKind.PHONE, 5, 15, 0.4)
    nhs = _cand(HitKind.NHS_NUMBER, 5, 15, 1.0)
    assert resolve_overlaps([date, dob]) == [dob]
    assert resolve_overlaps([phone, nhs]) == [nhs]
    assert resolve_overlaps([nhs, phone]) == [nhs]


def test_model_kinds_prefer_longer_then_score_then_enum_order():
    long_org = _cand(HitKind.ORGANISATION, 0, 18, 0.85)  # "Leeds City Council"
    short_loc = _cand(HitKind.LOCATION, 0, 5, 0.6)  # "Leeds"
    assert resolve_overlaps([short_loc, long_org]) == [long_org]
    person = _cand(HitKind.PERSON, 0, 7, 0.85)
    location = _cand(HitKind.LOCATION, 0, 7, 0.6)
    assert resolve_overlaps([location, person]) == [person]
    tie_person = _cand(HitKind.PERSON, 0, 7, 0.85)
    tie_loc = _cand(HitKind.LOCATION, 0, 7, 0.85)
    assert resolve_overlaps([tie_loc, tie_person]) == [tie_person]


def test_non_overlapping_candidates_are_all_kept_in_order():
    a = _cand(HitKind.PERSON, 10, 14)
    b = _cand(HitKind.LOCATION, 0, 5)
    c = _cand(HitKind.DATE, 20, 30)
    assert resolve_overlaps([a, b, c]) == [b, a, c]


def test_suppression_spans_whole_word_case_insensitive_and_patterns():
    text = "Report by DR IAN BROWN. MOTHER2FN met (LOCAL AUTHORITY). Browning Road."
    spans = suppression_spans(
        text,
        allowlist=["dr ian brown", " Brown "],
        placeholder_patterns=[r"\b[A-Z]{3,}\d[A-Z]{1,3}\b", r"\([A-Z][A-Z ]+\d?\)"],
    )
    assert (10, 22) in spans  # DR IAN BROWN
    assert (24, 33) in spans  # MOTHER2FN
    assert (38, 55) in spans  # (LOCAL AUTHORITY)
    assert not any(s <= 57 < e for s, e in spans)  # "Browning" is not "Brown"


def test_suppress_drops_contained_hits_only():
    spans = [(10, 22)]
    inside = _cand(HitKind.PERSON, 13, 22)  # "IAN BROWN" inside "DR IAN BROWN"
    straddling = _cand(HitKind.PERSON, 13, 30)
    outside = _cand(HitKind.PERSON, 40, 45)
    assert suppress([inside, straddling, outside], spans) == [straddling, outside]


def test_build_hits_fills_text_and_sorts():
    text = "Jane met Bob"
    cands = [
        _cand(HitKind.PERSON, 9, 12),
        _cand(HitKind.PERSON, 0, 4, 0.85, "SpacyRecognizer"),
    ]
    assert build_hits(text, cands) == [
        Hit(HitKind.PERSON, "Jane", 0, 4, 0.85, "SpacyRecognizer"),
        Hit(HitKind.PERSON, "Bob", 9, 12, 0.5, "R"),
    ]


def test_invalid_placeholder_pattern_raises_value_error():
    with pytest.raises(ValueError, match="placeholder"):
        suppression_spans("x", allowlist=[], placeholder_patterns=["("])


def test_allowlist_entry_with_regex_metacharacters_is_literal():
    spans = suppression_spans(
        "IDB Experts (UK) Ltd.",
        allowlist=["IDB Experts (UK) Ltd"],
        placeholder_patterns=[],
    )
    assert spans == [(0, 20)]
    assert re.escape("(") in re.escape("(UK)")
