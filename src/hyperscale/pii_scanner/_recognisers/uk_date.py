"""UK date formats as a Presidio pattern recogniser.

Bare years are not dates; spaCy's DATE label is disabled because it includes
durations such as "three weeks".
"""

from __future__ import annotations

from presidio_analyzer import Pattern
from presidio_analyzer import PatternRecognizer

MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?"
    r"|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
DAY = r"(?:0?[1-9]|[12][0-9]|3[01])"
ORDINAL = r"(?:st|nd|rd|th)?"
WEEKDAY = r"(?:(?:mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)day,?\s+)?"
YEAR = r"(?:19|20)\d{2}"
MONTH_NUM = r"(?:0?[1-9]|1[0-2])"

TEXTUAL_DMY = rf"{WEEKDAY}{DAY}{ORDINAL}\s+(?:of\s+)?{MONTH}\.?,?\s+{YEAR}"
TEXTUAL_MDY = rf"{WEEKDAY}{MONTH}\.?\s+{DAY}{ORDINAL},?\s+{YEAR}"
MONTH_YEAR = rf"{MONTH}\.?,?\s+{YEAR}"
# Dotted numeric dates need a four-digit year: "6.2.10" is a paragraph
# reference far more often than it is a date.
NUMERIC_DMY = (
    rf"(?:{DAY}[/-]{MONTH_NUM}[/-](?:{YEAR}|\d{{2}})|{DAY}\.{MONTH_NUM}\.{YEAR})"
)
# Any separator and a two-digit year; safe only after a label such as "DOB".
NUMERIC_DMY_LOOSE = rf"{DAY}[/.-]{MONTH_NUM}[/.-](?:{YEAR}|\d{{2}})"
ISO = rf"{YEAR}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"

# Any supported date form including the loose numeric one, unanchored, for
# use after a label such as "DOB". Callers add boundaries. Case-insensitive
# under Presidio's default flags.
ANY_DATE = rf"(?:{TEXTUAL_DMY}|{TEXTUAL_MDY}|{ISO}|{NUMERIC_DMY_LOOSE}|{MONTH_YEAR})"


class UkDateRecognizer(PatternRecognizer):
    """Recognise full dates and month-year pairs in UK conventions."""

    PATTERNS = [
        Pattern("textual day month year", rf"\b{TEXTUAL_DMY}\b", 0.85),
        Pattern("textual month day year", rf"\b{TEXTUAL_MDY}\b", 0.85),
        Pattern("month year", rf"\b{MONTH_YEAR}\b", 0.6),
        Pattern(
            "numeric day month year",
            rf"(?<![\d/-])(?<!\d\.){NUMERIC_DMY}(?![\d/-])(?!\.\d)",
            0.6,
        ),
        Pattern("iso date", rf"(?<![\d-]){ISO}(?![\d-])", 0.6),
    ]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="UK_DATE",
            name="UkDateRecognizer",
            patterns=self.PATTERNS,
        )
