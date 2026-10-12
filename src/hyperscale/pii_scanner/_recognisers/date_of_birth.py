"""A date that follows a date-of-birth label within 25 characters."""

from __future__ import annotations

import re

from presidio_analyzer import LocalRecognizer
from presidio_analyzer import RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from .uk_date import ANY_DATE

LABEL = r"(?:d\.?\s?o\.?\s?b\.?|date\s+of\s+birth|birth\s*date|born(?:\s+on|\s+in)?)"
PATTERN = re.compile(
    rf"(?<!\w){LABEL}(?!\w)[\s\S]{{0,25}}?(?<![\w/.-])({ANY_DATE})(?![\w/.-])",
    re.IGNORECASE,
)
SCORE = 0.9


class DateOfBirthRecognizer(LocalRecognizer):
    """Reports the date only, leaving the label in place for redaction."""

    def __init__(self) -> None:
        super().__init__(
            supported_entities=["DATE_OF_BIRTH"], name="DateOfBirthRecognizer"
        )

    def load(self) -> None:
        return None

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        if "DATE_OF_BIRTH" not in entities:
            return []
        return [
            RecognizerResult(
                entity_type="DATE_OF_BIRTH",
                start=match.start(1),
                end=match.end(1),
                score=SCORE,
                recognition_metadata={
                    RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                    RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id,
                },
            )
            for match in PATTERN.finditer(text)
        ]
