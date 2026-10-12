"""The public scan() entry point."""

from __future__ import annotations

from collections.abc import Iterable

from ._engine import analyze
from ._postprocess import build_hits
from ._postprocess import resolve_overlaps
from ._postprocess import suppress
from ._postprocess import suppression_spans
from ._postprocess import to_candidates
from ._postprocess import trim
from ._types import Hit


def scan(
    text: str,
    *,
    allowlist: Iterable[str] = (),
    placeholder_patterns: Iterable[str] = (),
    language: str = "en",
) -> list[Hit]:
    """Find residual personal identifiers in ``text``.

    Best effort: reports what the configured recognisers found. It never
    certifies that text is anonymised.
    """
    if language != "en":
        raise ValueError(f"unsupported language {language!r}; only 'en' is supported")
    allow = [entry.strip() for entry in allowlist if entry.strip()]
    patterns = list(placeholder_patterns)
    # Validate patterns up front so a bad pattern fails before the model loads.
    suppression_spans("", allow, patterns)
    if not text.strip():
        return []
    results = analyze(text)
    candidates = resolve_overlaps(trim(text, to_candidates(results)))
    spans = suppression_spans(text, allow, patterns)
    return build_hits(text, suppress(text, candidates, spans))
