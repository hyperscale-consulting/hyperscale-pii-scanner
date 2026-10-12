# pyright: reportPrivateUsage=false
import pytest

from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import scan
from hyperscale.pii_scanner._recognisers.date_of_birth import DateOfBirthRecognizer
from hyperscale.pii_scanner._recognisers.uk_date import UkDateRecognizer
from tests.helpers import matches


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("seen on 13th of July 2026", "13th of July 2026"),
        ("seen on 3rd June 2026", "3rd June 2026"),
        ("seen on 13 July 2026", "13 July 2026"),
        ("seen on 13 Jul 2026", "13 Jul 2026"),
        ("seen on 13 Sept 2026", "13 Sept 2026"),
        ("seen on Monday 13 July 2026", "Monday 13 July 2026"),
        ("seen on Monday, 13th July, 2026", "Monday, 13th July, 2026"),
        ("seen on July 13, 2026", "July 13, 2026"),
        ("seen on July 13th 2026", "July 13th 2026"),
        ("seen on 13/07/2026", "13/07/2026"),
        ("seen on 13/7/26", "13/7/26"),
        ("seen on 13.07.2026", "13.07.2026"),
        ("seen on 13-07-2026", "13-07-2026"),
        ("seen on 2026-07-13", "2026-07-13"),
        ("seen in July 2026", "July 2026"),
        ("seen in JULY 2026", "JULY 2026"),
        ("seen on 13/07/2026.", "13/07/2026"),
        ("seen on 2026-07-13.", "2026-07-13"),
        ("(DOB 14.3.19).", "14.3.19"),
    ],
)
def test_uk_date_positive(text: str, expected: str):
    found = [t for t, _ in matches(UkDateRecognizer(), text, "UK_DATE")]
    assert expected in found


@pytest.mark.parametrize(
    "text",
    [
        "in 2026 she moved",
        "ratio 32/7/2026",
        "13/13/2026",
        "three weeks later",
        "phone 0113 496 2026",
        "Section 13 of July",
    ],
)
def test_uk_date_negative(text: str):
    assert matches(UkDateRecognizer(), text, "UK_DATE") == []


def test_textual_dates_score_higher_than_numeric():
    textual = matches(UkDateRecognizer(), "13 July 2026", "UK_DATE")
    numeric = matches(UkDateRecognizer(), "13/07/2026", "UK_DATE")
    assert textual == [("13 July 2026", 0.85)]
    assert numeric == [("13/07/2026", 0.6)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("DOB: 14/03/2019", "14/03/2019"),
        ("DOB 14.3.19", "14.3.19"),
        ("D.O.B. 14 March 2019", "14 March 2019"),
        ("Date of birth: 14th of March 2019", "14th of March 2019"),
        ("date of birth 2019-03-14", "2019-03-14"),
        ("She was born on 14 March 2019 in Leeds", "14 March 2019"),
        ("born in March 2019", "March 2019"),
        ("Birth date - 14/03/2019", "14/03/2019"),
        ("date of birth is recorded as\n14/03/2019 on the form", "14/03/2019"),
        ("The youngest was born on 21 January 2024.", "21 January 2024"),
        ("DOB 14/03/2019.", "14/03/2019"),
    ],
)
def test_date_of_birth_positive(text: str, expected: str):
    assert matches(DateOfBirthRecognizer(), text, "DATE_OF_BIRTH") == [(expected, 0.9)]


@pytest.mark.parametrize(
    "text",
    [
        "DOB redacted",
        "seen on 14/03/2019",
        "born and raised in Leeds",
        "Reborn 14/03/2019",
        "DOB 2019",
    ],
)
def test_date_of_birth_negative(text: str):
    assert matches(DateOfBirthRecognizer(), text, "DATE_OF_BIRTH") == []


def test_scan_reports_dob_not_date_for_labelled_date():
    hits = scan("The child (DOB 14/03/2019) was seen on 13 July 2026.")
    by_text = {h.text: h.kind for h in hits}
    assert by_text["14/03/2019"] == HitKind.DATE_OF_BIRTH
    assert by_text["13 July 2026"] == HitKind.DATE
