# pyright: reportPrivateUsage=false
from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import scan
from hyperscale.pii_scanner._gazetteer import load_places
from hyperscale.pii_scanner._gazetteer import PlaceIndex
from hyperscale.pii_scanner._recognisers.gazetteer import UkGazetteerRecognizer
from tests.helpers import matches


def test_index_matches_whole_words_case_sensitive_longest_first():
    index = PlaceIndex(
        ["Leeds", "Newcastle upon Tyne", "Newcastle", "Tower Hamlets", "Hull"]
    )
    text = "Leeds, leeds, Leedsville, Newcastle upon Tyne, Tower Hamlets and Hull's."
    found = [text[s:e] for s, e in index.find(text)]
    assert found == ["Leeds", "Newcastle upon Tyne", "Tower Hamlets", "Hull"]


def test_index_handles_hyphen_and_apostrophe_names():
    index = PlaceIndex(["Stoke-on-Trent", "Bishop's Stortford"])
    text = "From Stoke-on-Trent to Bishop's Stortford."
    assert [text[s:e] for s, e in index.find(text)] == [
        "Stoke-on-Trent",
        "Bishop's Stortford",
    ]


def test_shipped_gazetteer_has_expected_entries_and_no_common_words():
    index = load_places()
    names = index.names
    for present in [
        "Harrogate",
        "Leeds",
        "London",
        "York",
        "Hackney",
        "Tower Hamlets",
        "Kent",
        "Newcastle upon Tyne",
        "Kingston upon Thames",
        "Caernarfon",
    ]:
        assert present in names, present
    for absent in [
        "Street",
        "Hope",
        "March",
        "Sale",
        "Reading",
        "Deal",
        "Wells",
        "Mold",
        "Ware",
        "Rye",
    ]:
        assert absent not in names, absent
    assert len(names) > 3000


def test_recogniser_reports_location_with_fixed_score():
    found = matches(UkGazetteerRecognizer(), "She moved to Harrogate.", "LOCATION")
    assert found == [("Harrogate", 0.9)]


def test_scan_reports_gazetteer_place_as_location_when_spacy_mislabels():
    hits = scan("Placement: Pontefract. The family moved to Cleckheaton last year.")
    found = {h.text: h.kind for h in hits}
    for place in ("Pontefract", "Cleckheaton"):
        assert found[place] == HitKind.LOCATION


def test_longer_spacy_person_span_beats_gazetteer_name():
    hits = scan("Jane Preston attended with her aunt.")
    kinds = {(h.kind, h.text) for h in hits}
    assert (HitKind.PERSON, "Jane Preston") in kinds
    assert not any(k == HitKind.LOCATION for k, _ in kinds)
