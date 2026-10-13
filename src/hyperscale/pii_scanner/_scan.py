"""The public scan() entry point."""

from __future__ import annotations

from collections.abc import Iterable

from ._engine import analyze
from ._postprocess import build_hits
from ._postprocess import drop_organisation_noise
from ._postprocess import resolve_overlaps
from ._postprocess import split_lines
from ._postprocess import suppress
from ._postprocess import suppression_spans
from ._postprocess import to_candidates
from ._postprocess import trim
from ._types import Hit
from ._types import HitKind


def scan(
    text: str,
    *,
    allowlist: Iterable[str] = (),
    placeholder_patterns: Iterable[str] = (),
    kinds: Iterable[HitKind | str] | None = None,
    language: str = "en",
) -> list[Hit]:
    """Find residual personal identifiers in ``text``.

    ``kinds`` limits the kinds reported; ``None`` means all of them. An excluded
    kind is treated as if its recogniser had not run, so it cannot hide an
    overlapping hit of a kept kind.

    Best effort: reports what the configured recognisers found. It never
    certifies that text is anonymised.
    """
    if language != "en":
        raise ValueError(f"unsupported language {language!r}; only 'en' is supported")
    if isinstance(allowlist, str):
        raise TypeError("allowlist must be an iterable of strings, not a single str")
    if isinstance(placeholder_patterns, str):
        raise TypeError(
            "placeholder_patterns must be an iterable of patterns, not a single str"
        )
    wanted = _parse_kinds(kinds)
    allow = [entry.strip() for entry in allowlist if entry.strip()]
    patterns = list(placeholder_patterns)
    # Validate patterns up front so a bad pattern fails before the model loads.
    suppression_spans("", allow, patterns)
    if not text.strip() or wanted == frozenset():
        return []
    results = analyze(text)
    candidates = split_lines(text, trim(text, to_candidates(results, wanted)))
    candidates = resolve_overlaps(drop_organisation_noise(text, candidates))
    spans = suppression_spans(text, allow, patterns)
    return build_hits(text, suppress(text, candidates, spans))


def _parse_kinds(kinds: Iterable[HitKind | str] | None) -> frozenset[HitKind] | None:
    if kinds is None:
        return None
    if isinstance(kinds, str):
        raise TypeError("kinds must be an iterable of HitKind, not a single str")
    try:
        return frozenset(HitKind(kind) for kind in kinds)
    except ValueError as exc:
        raise ValueError(f"unknown entry in kinds: {exc}") from exc
