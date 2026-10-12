"""Report gazetteer place names as LOCATION even when spaCy misses or mislabels them.

The score sits above spaCy's default 0.85 so an exact whole-word match of a known
UK place wins over a same-span PERSON or ORGANIZATION label; a longer spaCy span
(\"Jane Preston\", \"Leeds City Council\") still wins by length.
"""

from __future__ import annotations

from presidio_analyzer import LocalRecognizer
from presidio_analyzer import RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from .._gazetteer import load_places

SCORE = 0.9


class UkGazetteerRecognizer(LocalRecognizer):
    def __init__(self) -> None:
        super().__init__(supported_entities=["LOCATION"], name="UkGazetteerRecognizer")

    def load(self) -> None:
        load_places()

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        if "LOCATION" not in entities:
            return []
        return [
            RecognizerResult(
                entity_type="LOCATION",
                start=start,
                end=end,
                score=SCORE,
                recognition_metadata={
                    RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                    RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id,
                },
            )
            for start, end in load_places().find(text)
        ]
