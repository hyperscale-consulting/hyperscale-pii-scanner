"""Public value types."""

from __future__ import annotations

import enum
from dataclasses import dataclass


class HitKind(enum.StrEnum):
    """The closed set of identifier kinds the scanner reports.

    Member order is the final tie-break when two overlapping hits are otherwise equal.
    """

    PERSON = "person"
    LOCATION = "location"
    ORGANISATION = "organisation"
    DATE = "date"
    DATE_OF_BIRTH = "date_of_birth"
    AGE = "age"
    POSTCODE = "postcode"
    NHS_NUMBER = "nhs_number"
    NATIONAL_INSURANCE_NUMBER = "national_insurance_number"
    PHONE = "phone"
    EMAIL = "email"
    URL = "url"
    CASE_REFERENCE = "case_reference"


@dataclass(frozen=True, slots=True)
class Hit:
    """One identifier found in the scanned text.

    ``text`` is always ``source[start:end]``. ``recogniser`` names the Presidio
    recogniser that produced the hit, for example ``NhsRecognizer``.
    """

    kind: HitKind
    text: str
    start: int
    end: int
    score: float
    recogniser: str


@dataclass(frozen=True, slots=True)
class ScannerVersion:
    """Versions of every component that influences results, for audit logs."""

    library: str
    presidio_analyzer: str
    spacy: str
    model_name: str
    model_version: str

    def __str__(self) -> str:
        return (
            f"hyperscale-pii-scanner {self.library}; "
            f"presidio-analyzer {self.presidio_analyzer}; "
            f"spacy {self.spacy}; {self.model_name} {self.model_version}"
        )
