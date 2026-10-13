"""Turn Presidio results into non-overlapping, suppressed, sorted hits."""

from __future__ import annotations

import bisect
import re
from collections.abc import Collection
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


def to_candidates(
    results: Iterable[RecognizerResult], kinds: Collection[HitKind] | None = None
) -> list[Candidate]:
    """Map Presidio entity types to kinds; drop unknown kinds, low scores and,
    when ``kinds`` is given, every kind not in it."""
    candidates: list[Candidate] = []
    for result in results:
        kind = ENTITY_TO_KIND.get(result.entity_type)
        if kind is None or result.score < SCORE_THRESHOLD:
            continue
        if kinds is not None and kind not in kinds:
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


def resolve_overlaps(candidates: Iterable[Candidate]) -> list[Candidate]:
    """Keep one candidate per overlapping group using the spec's priority rules.

    Candidates are taken best-first, so a span that loses to a stronger
    neighbour never drags down a weaker one it merely happened to overlap.
    Kept spans are disjoint and held sorted by start, so each candidate is
    checked only against its two neighbours.
    """
    kept: list[Candidate] = []
    starts: list[int] = []
    best_first = sorted(
        candidates, key=lambda c: (_rank(c), -c.start, -c.end), reverse=True
    )
    for candidate in best_first:
        index = bisect.bisect_left(starts, candidate.start)
        if index > 0 and kept[index - 1].end > candidate.start:
            continue
        if index < len(kept) and kept[index].start < candidate.end:
            continue
        kept.insert(index, candidate)
        starts.insert(index, candidate.start)
    return kept


_TRIM_KINDS = frozenset({HitKind.PHONE, HitKind.URL, HitKind.EMAIL})
_TRAILING = ".,;:)"


def trim(text: str, candidates: Iterable[Candidate]) -> list[Candidate]:
    """Tidy phone, URL and email spans: drop an unbalanced leading "(" and trailing
    punctuation that the upstream matchers include ("(07700 123456", "example.org.")."""
    out: list[Candidate] = []
    for c in candidates:
        if c.kind not in _TRIM_KINDS:
            out.append(c)
            continue
        start, end = c.start, c.end
        while end > start and text[end - 1] in _TRAILING:
            if text[end - 1] == ")" and "(" in text[start:end]:
                break
            end -= 1
        while start < end and text[start] == "(" and ")" not in text[start:end]:
            start += 1
        if end > start:
            out.append(Candidate(c.kind, start, end, c.score, c.recogniser))
    return out


MODEL_KINDS = frozenset({HitKind.PERSON, HitKind.LOCATION, HitKind.ORGANISATION})
_LINE_BREAK = re.compile(r"[\r\n]")
_LINE_RUN = re.compile(r"[^\r\n]+")


def split_lines(text: str, candidates: Iterable[Candidate]) -> list[Candidate]:
    """Split model spans that run across a line break into one span per line.

    spaCy sometimes glues a header line to the start of the next ("MOTHER2FN
    MOTHER2SN\\nDate"). Each piece keeps the score; empty pieces are dropped.
    """
    out: list[Candidate] = []
    for c in candidates:
        span = text[c.start : c.end]
        if c.kind not in MODEL_KINDS or not _LINE_BREAK.search(span):
            out.append(c)
            continue
        for run in _LINE_RUN.finditer(text, c.start, c.end):
            piece = run.group()
            stripped = piece.strip()
            if stripped:
                start = run.start() + piece.index(stripped)
                out.append(
                    Candidate(
                        c.kind, start, start + len(stripped), c.score, c.recogniser
                    )
                )
    return out


# Six letters covers almost every test, scale and service acronym ("FSIQ",
# "CAMHS") while longer all-caps names ("CAFCASS") are still reported.
_ACRONYM = re.compile(r"[A-Z]{1,6}")
_HEADING_MAX_WORDS = 6
# A short line on its own is a heading unless it names an organisation type.
ORGANISATION_WORDS = frozenset(
    """
    academy agency association authority bank board centre center
    chambers charity church clinic college committee company consultants
    consulting co corporation council court department federation foundation
    group hospital housing inc institute limited llp ltd nhs nursery partners
    partnership plc police practice school service services society solicitors
    surgery trust union university
    """.split()
)


def _is_whole_short_line(text: str, start: int, end: int) -> bool:
    line_start = max(text.rfind("\n", 0, start), text.rfind("\r", 0, start)) + 1
    line_end = min(
        (i for i in (text.find("\n", end), text.find("\r", end)) if i != -1),
        default=len(text),
    )
    line = text[line_start:line_end]
    stripped = line.strip()
    if not stripped or len(stripped.split()) > _HEADING_MAX_WORDS:
        return False
    if start != line_start + line.index(stripped) or end != start + len(stripped):
        return False
    # A single line of text is not a document with headings.
    return bool(
        _LINE_RUN.search(text, 0, line_start) or _LINE_RUN.search(text, line_end)
    )


def drop_organisation_noise(
    text: str, candidates: Iterable[Candidate]
) -> list[Candidate]:
    """Drop organisation spans that are short all-caps acronyms, or a short
    heading-like line of their own with no organisation word in it."""
    out: list[Candidate] = []
    for c in candidates:
        if c.kind is HitKind.ORGANISATION:
            span = text[c.start : c.end]
            if _ACRONYM.fullmatch(span):
                continue
            words = {w.strip("'’.,:;()").lower() for w in span.split()}
            if not words & ORGANISATION_WORDS and _is_whole_short_line(
                text, c.start, c.end
            ):
                continue
        out.append(c)
    return out


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


_WORD = re.compile(r"\w+")
# Courtesy titles carry no identity of their own, so one in front of a
# placeholder or allowlisted name must not rescue the hit.
HONORIFICS = frozenset({"mr", "mrs", "ms", "miss", "mx", "dr", "prof"})


class _SpanIndex:
    """Suppression spans sorted by start, for neighbourhood lookups."""

    def __init__(self, spans: Iterable[tuple[int, int]]) -> None:
        self.spans = sorted(spans)
        self.starts = [s for s, _ in self.spans]
        self.longest = max((e - s for s, e in self.spans), default=0)

    def touching(self, start: int, end: int) -> list[tuple[int, int]]:
        """Spans that overlap [start, end)."""
        low = bisect.bisect_left(self.starts, start - self.longest)
        high = bisect.bisect_left(self.starts, end)
        return [(s, e) for s, e in self.spans[low:high] if e > start]


def _is_suppressed(text: str, candidate: Candidate, index: _SpanIndex) -> bool:
    """Whether allowlist or placeholder spans cover the candidate.

    A hit that touches a suppression span is suppressed when every token with a
    capital letter or digit lies inside one. Lowercase joining words ("and") and
    honorifics ("Ms") do not rescue a hit made only of placeholders; a
    capitalised leak ("MOTHER2FN Jones") does. A hit touching no span is never
    suppressed.
    """
    touching = index.touching(candidate.start, candidate.end)
    if not touching:
        return False
    for token in _WORD.finditer(text, candidate.start, candidate.end):
        covered = any(s <= token.start() and token.end() <= e for s, e in touching)
        word = token.group()
        if covered or word.lower() in HONORIFICS:
            continue
        if any(ch.isupper() or ch.isdigit() for ch in word):
            return False
    return True


def suppress(
    text: str, candidates: Iterable[Candidate], spans: Iterable[tuple[int, int]]
) -> list[Candidate]:
    """Drop candidates covered by allowlist or placeholder spans."""
    index = _SpanIndex(spans)
    return [c for c in candidates if not _is_suppressed(text, c, index)]


def build_hits(text: str, candidates: Iterable[Candidate]) -> list[Hit]:
    return [
        Hit(c.kind, text[c.start : c.end], c.start, c.end, c.score, c.recogniser)
        for c in sorted(candidates, key=lambda c: (c.start, c.end))
    ]
