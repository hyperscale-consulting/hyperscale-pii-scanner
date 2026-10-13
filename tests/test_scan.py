# pyright: reportPrivateUsage=false
import pytest

from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import scan
from hyperscale.pii_scanner._postprocess import suppression_spans

PLACEHOLDERS = [r"\b[A-Z]{3,}\d[A-Z]{1,3}\b", r"\([A-Z][A-Z ]+\d?\)"]


def test_scan_empty_text_returns_empty_list():
    assert scan("") == []
    assert scan("   \n") == []


def test_scan_rejects_other_languages():
    with pytest.raises(ValueError, match="language"):
        scan("Bonjour", language="fr")


def test_scan_validates_placeholder_patterns_before_scanning():
    with pytest.raises(ValueError, match="placeholder"):
        scan("Jane Smith", placeholder_patterns=["("])


def test_scan_reports_person_and_location():
    text = "Jane Smith lives in Harrogate."
    hits = scan(text)
    kinds = {(h.kind, h.text) for h in hits}
    assert (HitKind.PERSON, "Jane Smith") in kinds
    assert (HitKind.LOCATION, "Harrogate") in kinds
    for h in hits:
        assert text[h.start : h.end] == h.text


def test_scan_suppresses_allowlist_and_placeholders():
    text = (
        "Report by Dr Ian Brown. MOTHER2FN lives with (LOCAL AUTHORITY) support "
        "in Harrogate."
    )
    hits = scan(text, allowlist=["Dr Ian Brown"], placeholder_patterns=PLACEHOLDERS)
    texts = [h.text for h in hits]
    assert "Harrogate" in texts
    assert not any("Brown" in t for t in texts)
    assert not any("MOTHER2FN" in t or "LOCAL AUTHORITY" in t for t in texts)


def test_hit_extending_beyond_placeholder_is_reported():
    text = "The child was seen with MOTHER2FN Jones at home."
    hits = scan(text, placeholder_patterns=PLACEHOLDERS)
    assert any(h.kind == HitKind.PERSON and "Jones" in h.text for h in hits)


def test_scan_offsets_index_original_text_with_crlf_and_unicode():
    text = (
        "Report.\r\nLlanfairpwllgwyngyll is a village.\r\n"
        "Siân O’Neill attended with Jane Smith.\r\n"
    )
    hits = scan(text)
    assert hits, "expected at least one hit"
    for h in hits:
        assert text[h.start : h.end] == h.text
    assert any(h.kind == HitKind.PERSON and h.text == "Jane Smith" for h in hits)


def test_scan_results_are_sorted_and_non_overlapping():
    hits = scan(
        "Jane Smith met Bob Jones in Leeds on 13 July 2026 near Leeds City Council."
    )
    for earlier, later in zip(hits, hits[1:], strict=False):
        assert earlier.end <= later.start


def test_scan_is_deterministic():
    text = "Jane Smith lives in Harrogate and works for Leeds City Council."
    assert scan(text) == scan(text)


def test_whitespace_only_allowlist_entries_are_ignored():
    assert (
        suppression_spans("Jane", allowlist=["  ", ""], placeholder_patterns=[]) == []
    )


def test_scan_trims_phone_in_parentheses_and_url_before_full_stop():
    hits = scan("Call her (07700 123456). See https://www.example.org/cases/12345.")
    found = {h.kind: h.text for h in hits}
    assert found[HitKind.PHONE] == "07700 123456"
    assert found[HitKind.URL] == "https://www.example.org/cases/12345"


def test_facilities_are_reported_as_locations():
    hits = scan("She was seen at Heathrow Airport and later near the Humber Bridge.")
    found = {h.text for h in hits if h.kind == HitKind.LOCATION}
    assert "Heathrow Airport" in found


def test_scan_rejects_bare_string_allowlist_and_patterns():
    with pytest.raises(TypeError, match="allowlist"):
        scan("Jane Smith", allowlist="Dr Ian Brown")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="placeholder_patterns"):
        scan("Jane Smith", placeholder_patterns=r"\bX\d\b")  # type: ignore[arg-type]


def test_honorific_before_placeholder_is_suppressed():
    text = "Ms MOTHER2SN attended the session with Mr FATHER1SN."
    assert scan(text, placeholder_patterns=PLACEHOLDERS) == []


def test_placeholder_in_header_line_is_not_glued_to_the_next_line():
    text = (
        "Psychological report on MOTHER2FN MOTHER2SN\nDate of assessment: 3 June 2026"
    )
    hits = scan(text, placeholder_patterns=PLACEHOLDERS)
    assert not any("MOTHER2SN" in h.text for h in hits)
    assert all("\n" not in h.text for h in hits)


REPORT = (
    "Psychological report on MOTHER2FN MOTHER2SN\nDate of assessment: 3 June 2026\n\n"
    "Background Information\n\nShe was referred by Westfield Medical Practice.\n\n"
    "Verbal Comprehension\n\nShe scored well on the VCI and the FSIQ was average. "
    "The GAI, WMI and PRI were also average."
)
NOISE = {
    "Background Information",
    "Verbal Comprehension",
    "VCI",
    "FSIQ",
    "GAI",
    "WMI",
    "PRI",
}


def test_headings_and_test_acronyms_are_not_reported_as_organisations():
    hits = scan(REPORT, placeholder_patterns=PLACEHOLDERS)
    orgs = {h.text for h in hits if h.kind == HitKind.ORGANISATION}
    assert "Westfield Medical Practice" in orgs
    assert not orgs & NOISE


def test_scan_kinds_limits_the_kinds_reported():
    text = "Jane Smith of Westfield Medical Practice lives in Harrogate, HG1 1AA."
    hits = scan(text, kinds={HitKind.PERSON, HitKind.POSTCODE})
    assert {h.kind for h in hits} == {HitKind.PERSON, HitKind.POSTCODE}
    assert scan(text, kinds=[]) == []


def test_scan_kinds_accepts_string_values_and_rejects_unknown_ones():
    hits = scan("Jane Smith lives in Harrogate.", kinds=["location"])
    assert [(h.kind, h.text) for h in hits] == [(HitKind.LOCATION, "Harrogate")]
    with pytest.raises(ValueError, match="kinds"):
        scan("Jane Smith", kinds=["name"])


def test_excluded_kind_does_not_hide_an_overlapping_kept_kind():
    # The model may label "Harrogate, HG1" as one organisation; with
    # organisations excluded the gazetteer location underneath must survive.
    text = "12 Station Parade, Harrogate, HG1 1AA"
    hits = scan(text, kinds=set(HitKind) - {HitKind.ORGANISATION})
    assert (HitKind.LOCATION, "Harrogate") in {(h.kind, h.text) for h in hits}
