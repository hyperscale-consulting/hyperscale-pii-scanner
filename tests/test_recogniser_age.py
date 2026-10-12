# pyright: reportPrivateUsage=false
import pytest

from hyperscale.pii_scanner._recognisers.age import AgeRecognizer
from tests.helpers import matches


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("she is aged 34", "aged 34"),
        ("she is aged 34 years", "aged 34 years"),
        ("Age: 34", "Age: 34"),
        ("age 34", "age 34"),
        ("she is 34 years old", "34 years old"),
        ("a 34-year-old woman", "34-year-old"),
        ("a 34 year old woman", "34 year old"),
        ("34 yrs old", "34 yrs old"),
        ("aged 18 months", "aged 18 months"),
        ("an 18-month-old baby", "18-month-old"),
        ("a six-year-old boy", "six-year-old"),
        ("aged six", "aged six"),
        ("twenty-one years of age", "twenty-one years of age"),
        ("AGED 34", "AGED 34"),
    ],
)
def test_age_positive(text: str, expected: str):
    assert matches(AgeRecognizer(), text, "AGE") == [(expected, 0.7)]


@pytest.mark.parametrize(
    "text",
    [
        "aged 250",
        "page 34",
        "stage 2 assessment",
        "34 years ago",
        "for 34 years",
        "the old 34 bus",
        "an image 34 years in the making",
    ],
)
def test_age_negative(text: str):
    assert matches(AgeRecognizer(), text, "AGE") == []
