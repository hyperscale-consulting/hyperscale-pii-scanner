"""Builds the explicit Presidio recogniser registry.

Only recognisers listed here run. Presidio's defaults are never loaded, so a
Presidio upgrade cannot re-enable US-centric recognisers.
"""

from __future__ import annotations

from presidio_analyzer import EntityRecognizer
from presidio_analyzer import RecognizerRegistry
from presidio_analyzer.predefined_recognizers import NhsRecognizer
from presidio_analyzer.predefined_recognizers import PhoneRecognizer
from presidio_analyzer.predefined_recognizers import SpacyRecognizer
from presidio_analyzer.predefined_recognizers import UrlRecognizer

from .age import AgeRecognizer
from .case_reference import CaseReferenceRecognizer
from .date_of_birth import DateOfBirthRecognizer
from .email import OfflineEmailRecognizer
from .nino import UkNinoRecognizer
from .postcode import UkPostcodeRecognizer
from .uk_date import UkDateRecognizer

SPACY_ENTITIES = ["PERSON", "LOCATION", "ORGANIZATION"]
PHONE_REGIONS = ("GB",)


def build_recognisers() -> list[EntityRecognizer]:
    return [
        SpacyRecognizer(supported_entities=SPACY_ENTITIES),
        UkDateRecognizer(),
        DateOfBirthRecognizer(),
        AgeRecognizer(),
        UkPostcodeRecognizer(),
        NhsRecognizer(),
        UkNinoRecognizer(),
        PhoneRecognizer(supported_regions=PHONE_REGIONS),
        OfflineEmailRecognizer(),
        UrlRecognizer(),
        CaseReferenceRecognizer(),
    ]


def build_registry() -> RecognizerRegistry:
    return RecognizerRegistry(
        recognizers=build_recognisers(), supported_languages=["en"]
    )
