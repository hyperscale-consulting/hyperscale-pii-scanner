import pytest

from hyperscale.pii_scanner import Hit
from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import redact


def _hit(kind: HitKind, text: str, start: int) -> Hit:
    return Hit(kind, text, start, start + len(text), 0.9, "test")


def test_redact_default_token_is_upper_kind_in_brackets():
    text = "Jane Smith, NHS 943 476 5919."
    hits = [
        _hit(HitKind.PERSON, "Jane Smith", 0),
        _hit(HitKind.NHS_NUMBER, "943 476 5919", 16),
    ]
    assert redact(text, hits) == "[PERSON], NHS [NHS_NUMBER]."


def test_redact_custom_token_receives_the_hit():
    text = "Jane Smith"
    hits = [_hit(HitKind.PERSON, "Jane Smith", 0)]
    assert redact(text, hits, token_for=lambda h: f"<{h.kind}:{len(h.text)}>") == (
        "<person:10>"
    )


def test_redact_with_no_hits_returns_text_unchanged():
    assert redact("nothing here", []) == "nothing here"


def test_redact_rejects_hits_from_other_text():
    with pytest.raises(ValueError, match="does not match"):
        redact("Bob Jones is here", [_hit(HitKind.PERSON, "Jane Smith", 0)])


def test_redact_rejects_out_of_range_hit():
    with pytest.raises(ValueError):
        redact("short", [Hit(HitKind.PERSON, "longer text", 0, 11, 0.9, "t")])


def test_redact_overlapping_hits_keeps_earliest_then_longest():
    text = "Leeds City Council"
    hits = [
        _hit(HitKind.LOCATION, "Leeds", 0),
        _hit(HitKind.ORGANISATION, "Leeds City Council", 0),
    ]
    assert redact(text, hits) == "[ORGANISATION]"
    hits = [
        _hit(HitKind.ORGANISATION, "City Council", 6),
        _hit(HitKind.LOCATION, "Leeds City", 0),
    ]
    assert redact(text, hits) == "[LOCATION] Council"


def test_redact_handles_unordered_input():
    text = "A Jane and Bob"
    hits = [_hit(HitKind.PERSON, "Bob", 11), _hit(HitKind.PERSON, "Jane", 2)]
    assert redact(text, hits) == "A [PERSON] and [PERSON]"
