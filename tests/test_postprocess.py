# pyright: reportPrivateUsage=false
import re

import pytest
from presidio_analyzer import RecognizerResult

from hyperscale.pii_scanner import Hit
from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner._postprocess import build_hits
from hyperscale.pii_scanner._postprocess import Candidate
from hyperscale.pii_scanner._postprocess import drop_organisation_noise
from hyperscale.pii_scanner._postprocess import resolve_overlaps
from hyperscale.pii_scanner._postprocess import split_lines
from hyperscale.pii_scanner._postprocess import suppress
from hyperscale.pii_scanner._postprocess import suppression_spans
from hyperscale.pii_scanner._postprocess import to_candidates
from hyperscale.pii_scanner._postprocess import trim


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
    text = "Report by DR IAN BROWN. MOTHER2FN met (LOCAL AUTHORITY). Browning Road."
    straddling = _cand(HitKind.PERSON, 13, 30)  # "IAN BROWN. MOTHER"
    outside = _cand(HitKind.PERSON, 57, 65)  # "Browning"
    assert suppress(text, [inside, straddling, outside], spans) == [straddling, outside]


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


def test_candidate_beaten_by_a_span_that_later_loses_is_still_kept():
    # "12 Station Parade, Harrogate, HG1 1AA": spaCy ORG "Harrogate, HG1" beats
    # the gazetteer "Harrogate" by length, then loses to the postcode. The
    # location must survive.
    org = _cand(HitKind.ORGANISATION, 19, 33, 0.85)
    loc = _cand(HitKind.LOCATION, 19, 28, 0.9)
    postcode = _cand(HitKind.POSTCODE, 30, 37, 0.6)
    assert resolve_overlaps([org, loc, postcode]) == [loc, postcode]


def test_trim_strips_unbalanced_leading_paren_and_trailing_punctuation():
    text = "call (07700 123456) or see https://example.org/x. Email a@b.org, thanks"
    phone = _cand(HitKind.PHONE, 5, 18)  # "(07700 123456"
    url = _cand(HitKind.URL, 27, 49)  # "https://example.org/x."
    email = _cand(HitKind.EMAIL, 56, 64)  # "a@b.org,"
    person = _cand(HitKind.PERSON, 0, 5)  # untouched kinds keep their span
    trimmed = trim(text, [phone, url, email, person])
    assert [text[c.start : c.end] for c in trimmed] == [
        "07700 123456",
        "https://example.org/x",
        "a@b.org",
        "call ",
    ]


def test_suppress_drops_hit_whose_only_uncovered_tokens_are_lowercase():
    text = "MOTHER2FN MOTHER2SN and FATHER1FN FATHER1SN met MOTHER2FN Jones"
    spans = suppression_spans(
        text, allowlist=[], placeholder_patterns=[r"\b[A-Z]{3,}\d[A-Z]{1,3}\b"]
    )
    merged = _cand(HitKind.PERSON, 0, 43)  # placeholders joined by "and"
    leak = _cand(HitKind.PERSON, 48, 63)  # "MOTHER2FN Jones"
    assert suppress(text, [merged, leak], spans) == [leak]


def test_resolve_overlaps_and_suppress_scale_to_many_candidates():
    import time

    count = 20_000
    cands = [_cand(HitKind.DATE, i * 12, i * 12 + 10, 0.6) for i in range(count)]
    cands += [_cand(HitKind.PERSON, i * 12 + 2, i * 12 + 6, 0.85) for i in range(count)]
    spans = [(i * 12 + 1, i * 12 + 3) for i in range(0, count, 7)]
    text = "A" * (count * 12)
    started = time.perf_counter()
    kept = resolve_overlaps(cands)
    survivors = suppress(text, kept, spans)
    elapsed = time.perf_counter() - started
    assert len(kept) == count
    assert all(c.kind == HitKind.DATE for c in kept)
    assert len(survivors) == count
    assert elapsed < 2.0, f"took {elapsed:.2f}s"


PLACEHOLDER = [r"\b[A-Z]{3,}\d[A-Z]{1,3}\b"]


@pytest.mark.parametrize(
    "honorific", ["Ms", "Mr", "Mrs", "Miss", "Mx", "Dr", "Dr.", "Prof"]
)
def test_suppress_treats_honorific_before_placeholder_as_neutral(honorific: str):
    text = f"{honorific} MOTHER2SN attended."
    spans = suppression_spans(text, allowlist=[], placeholder_patterns=PLACEHOLDER)
    end = len(honorific) + 1 + len("MOTHER2SN")
    assert suppress(text, [_cand(HitKind.PERSON, 0, end)], spans) == []


def test_suppress_keeps_honorific_followed_by_a_real_surname():
    text = "Ms MOTHER2SN and Ms Hartley attended."
    spans = suppression_spans(text, allowlist=[], placeholder_patterns=PLACEHOLDER)
    glued = _cand(HitKind.PERSON, 0, 27)  # "Ms MOTHER2SN and Ms Hartley"
    assert suppress(text, [glued], spans) == [glued]


def test_suppress_treats_honorific_before_allowlisted_name_as_neutral():
    text = "Report by Dr Ian Brown."
    spans = suppression_spans(text, allowlist=["Ian Brown"], placeholder_patterns=[])
    assert suppress(text, [_cand(HitKind.PERSON, 10, 22)], spans) == []


def test_split_lines_splits_model_spans_at_newlines_and_strips_whitespace():
    text = "MOTHER2FN MOTHER2SN\nDate of assessment\r\n\nJane"
    org = _cand(HitKind.ORGANISATION, 0, 24)  # "MOTHER2FN MOTHER2SN\nDate"
    person = _cand(HitKind.PERSON, 19, 45)  # "\nDate of assessment\r\n\nJane"
    pieces = split_lines(text, [org, person])
    assert [(c.kind, text[c.start : c.end]) for c in pieces] == [
        (HitKind.ORGANISATION, "MOTHER2FN MOTHER2SN"),
        (HitKind.ORGANISATION, "Date"),
        (HitKind.PERSON, "Date of assessment"),
        (HitKind.PERSON, "Jane"),
    ]
    assert all(c.score == org.score and c.recogniser == org.recogniser for c in pieces)


def test_split_lines_leaves_structured_kinds_and_single_line_spans_alone():
    text = "DOB 14\nMarch 2019; Jane Smith"
    dob = _cand(HitKind.DATE_OF_BIRTH, 4, 17)
    person = _cand(HitKind.PERSON, 19, 29)
    assert split_lines(text, [dob, person]) == [dob, person]


def test_to_candidates_keeps_only_requested_kinds():
    results = [
        _result("PERSON", 0, 4, 0.85),
        _result("ORGANIZATION", 5, 15, 0.85),
        _result("UK_NHS", 16, 28, 1.0),
    ]
    kept = to_candidates(results, kinds={HitKind.PERSON, HitKind.NHS_NUMBER})
    assert [c.kind for c in kept] == [HitKind.PERSON, HitKind.NHS_NUMBER]


def _org_texts(text: str, *spans: tuple[int, int]) -> list[str]:
    cands = [_cand(HitKind.ORGANISATION, s, e, 0.85) for s, e in spans]
    return [text[c.start : c.end] for c in drop_organisation_noise(text, cands)]


@pytest.mark.parametrize("acronym", ["FSIQ", "GAI", "NHS", "GP", "CAMHS", "TOPF"])
def test_short_all_caps_acronym_is_not_an_organisation(acronym: str):
    text = f"The {acronym} score was average."
    assert _org_texts(text, (4, 4 + len(acronym))) == []


@pytest.mark.parametrize("name", ["CAFCASS", "WISC-V", "Ofsted", "BBC Radio"])
def test_longer_or_mixed_all_caps_spans_are_kept(name: str):
    text = f"Referred by {name} last year."
    assert _org_texts(text, (12, 12 + len(name))) == [name]


def test_short_heading_line_in_multi_line_text_is_not_an_organisation():
    text = "Intro line.\n\nBackground Information\n\nVerbal Comprehension\nMore."
    assert _org_texts(text, (13, 35), (37, 57)) == []


def test_letterhead_line_with_organisation_word_is_kept():
    text = "Westfield Medical Practice\n12 Station Parade\nHarrogate"
    assert _org_texts(text, (0, 26)) == ["Westfield Medical Practice"]


def test_whole_line_rule_does_not_apply_to_single_line_text():
    text = "Acme Widgets"
    assert _org_texts(text, (0, 12)) == ["Acme Widgets"]


def test_whole_line_rule_does_not_apply_to_long_lines_or_partial_lines():
    long_line = "Northern Independent Assessment and Therapy Services Partnership"
    text = f"Heading\n{long_line}\nSeen by Acme Widgets today"
    start = len("Heading\n")
    partial = text.index("Acme Widgets")
    assert _org_texts(
        text, (start, start + len(long_line)), (partial, partial + 12)
    ) == [
        long_line,
        "Acme Widgets",
    ]


def test_drop_organisation_noise_leaves_other_kinds_alone():
    text = "Intro.\nJane Smith\nLeeds"
    person = _cand(HitKind.PERSON, 7, 17)
    place = _cand(HitKind.LOCATION, 18, 23)
    assert drop_organisation_noise(text, [person, place]) == [person, place]
