from typing import cast
from typing import Protocol

from presidio_analyzer import EntityRecognizer
from presidio_analyzer import RecognizerResult


class _Analyzes(Protocol):
    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: None = None
    ) -> list[RecognizerResult]: ...


def matches(
    recogniser: EntityRecognizer, text: str, entity: str
) -> list[tuple[str, float]]:
    """Run one recogniser directly (no NLP artifacts) and return (text, score) pairs."""
    results = cast(_Analyzes, recogniser).analyze(text, [entity], None)
    return sorted((text[r.start : r.end], round(r.score, 2)) for r in results)
