"""Turn Presidio results into non-overlapping, suppressed, sorted hits."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from presidio_analyzer import RecognizerResult

from ._engine import SCORE_THRESHOLD
from ._types import Hit
from ._types import HitKind

ENTITY_TO_KIND: dict[str, HitKind] = {
    "PERSON": HitKind.PERSON,
    "LOCATION": HitKind.LOCATION,
    "ORGANIZATION": HitKind.ORGANISATION,
    "UK_DATE": HitKind.DATE,
    "DATE_OF_BIRTH": HitKind.DATE_OF_BIRTH,
    "AGE": HitKind.AGE,
    "UK_POSTCODE": HitKind.POSTCODE,
    "UK_NHS": HitKind.NHS_NUMBER,
    "UK_NINO": HitKind.NATIONAL_INSURANCE_NUMBER,
    "PHONE_NUMBER": HitKind.PHONE,
    "EMAIL_ADDRESS": HitKind.EMAIL,
    "URL": HitKind.URL,
    "CASE_REFERENCE": HitKind.CASE_REFERENCE,
}

# Highest priority first. Kinds not listed are "model" kinds.
STRUCTURED_PRIORITY: tuple[HitKind, ...] = (
    HitKind.DATE_OF_BIRTH,
    HitKind.NHS_NUMBER,
    HitKind.NATIONAL_INSURANCE_NUMBER,
    HitKind.POSTCODE,
    HitKind.CASE_REFERENCE,
    HitKind.EMAIL,
    HitKind.URL,
    HitKind.PHONE,
    HitKind.AGE,
    HitKind.DATE,
)
_KIND_ORDER = {kind: index for index, kind in enumerate(HitKind)}


@dataclass(frozen=True, slots=True)
class Candidate:
    kind: HitKind
    start: int
    end: int
    score: float
    recogniser: str


def to_candidates(results: Iterable[RecognizerResult]) -> list[Candidate]:
    """Map Presidio entity types to kinds; drop unknown kinds and low scores."""
    candidates: list[Candidate] = []
    for result in results:
        kind = ENTITY_TO_KIND.get(result.entity_type)
        if kind is None or result.score < SCORE_THRESHOLD:
            continue
        raw: object = getattr(result, "recognition_metadata", None)
        metadata = cast("dict[str, object]", raw) if isinstance(raw, dict) else {}
        name = str(metadata.get(RecognizerResult.RECOGNIZER_NAME_KEY, "unknown"))
        candidates.append(
            Candidate(kind, result.start, result.end, float(result.score), name)
        )
    return candidates


def _rank(candidate: Candidate) -> tuple[int, int, int, float, int]:
    structured = candidate.kind in STRUCTURED_PRIORITY
    priority = -STRUCTURED_PRIORITY.index(candidate.kind) if structured else 0
    return (
        1 if structured else 0,
        priority,
        candidate.end - candidate.start,
        candidate.score,
        -_KIND_ORDER[candidate.kind],
    )


def _overlaps(a: Candidate, b: Candidate) -> bool:
    return a.start < b.end and b.start < a.end


def resolve_overlaps(candidates: Iterable[Candidate]) -> list[Candidate]:
    """Keep one candidate per overlapping group using the spec's priority rules."""
    kept: list[Candidate] = []
    for candidate in sorted(candidates, key=lambda c: (c.start, -(c.end - c.start))):
        conflicts = [k for k in kept if _overlaps(k, candidate)]
        if not conflicts:
            kept.append(candidate)
            continue
        if all(_rank(candidate) > _rank(other) for other in conflicts):
            kept = [k for k in kept if k not in conflicts]
            kept.append(candidate)
    return sorted(kept, key=lambda c: (c.start, c.end))


def suppression_spans(
    text: str,
    allowlist: Iterable[str],
    placeholder_patterns: Iterable[str],
) -> list[tuple[int, int]]:
    """Spans of allowlist occurrences (whole word, case-insensitive) and placeholder
    matches.

    Raises ``ValueError`` for an invalid placeholder pattern.
    """
    spans: list[tuple[int, int]] = []
    for entry in allowlist:
        entry = entry.strip()
        if not entry:
            continue
        pattern = re.compile(r"(?<!\w)" + re.escape(entry) + r"(?!\w)", re.IGNORECASE)
        spans.extend(m.span() for m in pattern.finditer(text))
    for raw in placeholder_patterns:
        try:
            pattern = re.compile(raw)
        except re.error as exc:
            raise ValueError(f"invalid placeholder pattern {raw!r}: {exc}") from exc
        spans.extend(m.span() for m in pattern.finditer(text) if m.end() > m.start())
    return spans


def suppress(
    candidates: Iterable[Candidate], spans: Iterable[tuple[int, int]]
) -> list[Candidate]:
    """Drop candidates whose span lies entirely within a suppression span."""
    span_list = list(spans)
    return [
        c
        for c in candidates
        if not any(start <= c.start and c.end <= end for start, end in span_list)
    ]


def build_hits(text: str, candidates: Iterable[Candidate]) -> list[Hit]:
    return [
        Hit(c.kind, text[c.start : c.end], c.start, c.end, c.score, c.recogniser)
        for c in sorted(candidates, key=lambda c: (c.start, c.end))
    ]
