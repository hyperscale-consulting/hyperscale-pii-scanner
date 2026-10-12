"""UK postcodes: full form on its own, outward code only with a context word."""

from __future__ import annotations

from presidio_analyzer import Pattern
from presidio_analyzer import PatternRecognizer

# Position rules from https://en.wikipedia.org/wiki/Postcodes_in_the_United_Kingdom
AREA_DISTRICT = (
    r"(?:[A-PR-UWYZ]"
    r"(?:\d{1,2}|[A-HK-Y]\d{1,2}|\d[A-HJKPSTUW]|[A-HK-Y]\d[ABEHMNPRVWXY]))"
)
INWARD = r"\d[ABD-HJLNP-UW-Z]{2}"


class UkPostcodeRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern(
            "full postcode", rf"(?-i:\b(?:GIR 0AA|{AREA_DISTRICT} {INWARD})\b)", 0.6
        ),
        Pattern(
            "full postcode, no space",
            rf"(?-i:\b(?:GIR0AA|{AREA_DISTRICT}{INWARD})\b)",
            0.45,
        ),
        Pattern("outward code", rf"(?-i:\b{AREA_DISTRICT}\b(?! ?{INWARD}\b))", 0.05),
    ]
    CONTEXT = ["postcode", "post code", "postal", "area", "district"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="UK_POSTCODE",
            name="UkPostcodeRecognizer",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )
