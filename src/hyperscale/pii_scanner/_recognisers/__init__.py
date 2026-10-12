"""Builds the explicit Presidio recogniser registry.

Only recognisers listed here run. Presidio's defaults are never loaded, so a
Presidio upgrade cannot re-enable US-centric recognisers.
"""

from __future__ import annotations

from presidio_analyzer import EntityRecognizer
from presidio_analyzer import RecognizerRegistry
from presidio_analyzer.predefined_recognizers import SpacyRecognizer

from .age import AgeRecognizer
from .date_of_birth import DateOfBirthRecognizer
from .uk_date import UkDateRecognizer

SPACY_ENTITIES = ["PERSON", "LOCATION", "ORGANIZATION"]


def build_recognisers() -> list[EntityRecognizer]:
    return [
        SpacyRecognizer(supported_entities=SPACY_ENTITIES),
        UkDateRecognizer(),
        DateOfBirthRecognizer(),
        AgeRecognizer(),
    ]


def build_registry() -> RecognizerRegistry:
    return RecognizerRegistry(
        recognizers=build_recognisers(), supported_languages=["en"]
    )
