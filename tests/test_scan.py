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
