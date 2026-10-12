import dataclasses

import pytest

from hyperscale.pii_scanner import Hit
from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import ScannerVersion


def test_hit_kind_members_and_order():
    assert [k.value for k in HitKind] == [
        "person",
        "location",
        "organisation",
        "date",
        "date_of_birth",
        "age",
        "postcode",
        "nhs_number",
        "national_insurance_number",
        "phone",
        "email",
        "url",
        "case_reference",
    ]
    assert HitKind("nhs_number") is HitKind.NHS_NUMBER
    assert str(HitKind.PERSON) == "person"


def test_hit_is_frozen_and_hashable():
    hit = Hit(HitKind.PERSON, "Jane", 0, 4, 0.85, "SpacyRecognizer")
    with pytest.raises(dataclasses.FrozenInstanceError):
        hit.text = "x"  # type: ignore[misc]
    assert hash(hit) == hash(Hit(HitKind.PERSON, "Jane", 0, 4, 0.85, "SpacyRecognizer"))


def test_scanner_version_str_is_one_audit_line():
    v = ScannerVersion("0.1.0", "2.2.364", "3.8.16", "en_core_web_md", "3.8.0")
    assert str(v) == (
        "hyperscale-pii-scanner 0.1.0; presidio-analyzer 2.2.364; "
        "spacy 3.8.16; en_core_web_md 3.8.0"
    )
