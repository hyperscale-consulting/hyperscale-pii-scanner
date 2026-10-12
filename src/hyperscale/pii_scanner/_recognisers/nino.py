"""UK National Insurance numbers with the prefix and suffix rules.

Presidio's own UkNinoRecognizer allows an optional space between the word
boundary and the first letter, which both defeats its forbidden-prefix lookahead
("number BG123456C" matches as " BG123456C") and puts the space inside the span.
This recogniser keeps Presidio's letter classes without that defect.
"""

from __future__ import annotations

from presidio_analyzer import Pattern
from presidio_analyzer import PatternRecognizer

# First letter: not D, F, I, Q, U, V. Second letter: additionally not O.
# Prefixes BG, GB, NK, KN, NT, TN and ZZ are not allocated. Suffix A to D.
NINO = (
    r"\b(?!(?:BG|GB|NK|KN|NT|TN|ZZ))"
    r"[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z] ?\d{2} ?\d{2} ?\d{2} ?[A-D]\b"
)


class UkNinoRecognizer(PatternRecognizer):
    PATTERNS = [Pattern("NINO", rf"(?-i:{NINO})", 0.5)]
    CONTEXT = ["national insurance", "ni number", "nino"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="UK_NINO",
            name="UkNinoRecognizer",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )
