"""Court and case references in the common UK patterns."""

from __future__ import annotations

from presidio_analyzer import Pattern
from presidio_analyzer import PatternRecognizer

COURTS = (
    r"(?:UKSC|UKPC|UKHL|UKUT|UKFTT|UKEAT|EWCA(?:\s+(?:Civ|Crim))?|EWHC|EWFC|EWCOP|EWCC"
    r"|CSOH|CSIH|NICA|NIQB|NIFam)"
)


class CaseReferenceRecognizer(PatternRecognizer):
    PATTERNS = [
        # Family, county and civil court case numbers: ZC24C50123, FD24P00123
        Pattern("court case number", r"(?-i:\b[A-Z]{2}\d{2}[A-Z]\d{5}\b)", 0.7),
        # Neutral citations: [2026] EWFC 12, [2024] EWHC 123 (Fam), [2023] EWCA Civ 45
        Pattern(
            "neutral citation",
            rf"(?-i:\[(?:19|20)\d{{2}}\]\s+{COURTS}\s+\d+(?:\s+\([A-Za-z]+\))?)",
            0.85,
        ),
        # Crown Court numbers (T20247123) and CPS URNs (01AB1234567): context required
        Pattern(
            "crown court or cps number",
            r"(?-i:\b(?:[TSU]\d{8}|\d{2}[A-Z]{2}\d{5,7})\b)",
            0.2,
        ),
    ]
    CONTEXT = ["case", "urn", "reference", "ref", "number"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="CASE_REFERENCE",
            name="CaseReferenceRecognizer",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )
