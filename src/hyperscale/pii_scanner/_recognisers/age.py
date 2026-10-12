"""Ages: "aged 34", "34 years old", "34-year-old", "six-year-old", "18 months old"."""

from __future__ import annotations

import re

from presidio_analyzer import Pattern
from presidio_analyzer import PatternRecognizer

NUMBER_WORDS = (
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    "fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|"
    "fifty|sixty|seventy|eighty|ninety"
)
NUM = rf"(?:\d{{1,3}}|(?:{NUMBER_WORDS})(?:[\s-](?:{NUMBER_WORDS}))?)"
UNIT = r"(?:years?|yrs?|months?|weeks?)"
MAX_AGE = 120


class AgeRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("aged N", rf"\baged?\s*:?\s*{NUM}(?:\s*{UNIT})?\b", 0.7),
        Pattern("N years old", rf"\b{NUM}[\s-]+{UNIT}[\s-]+old\b", 0.7),
        Pattern("N years of age", rf"\b{NUM}\s+{UNIT}\s+of\s+age\b", 0.7),
    ]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="AGE", name="AgeRecognizer", patterns=self.PATTERNS
        )

    def invalidate_result(self, pattern_text: str) -> bool:
        """Numbers above 120 are not ages."""
        digits = re.search(r"\d+", pattern_text)
        return digits is not None and int(digits.group()) > MAX_AGE
