"""Replace hits in text with tokens."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterable

from ._types import Hit


def _default_token(hit: Hit) -> str:
    return f"[{hit.kind.value.upper()}]"


def redact(
    text: str, hits: Iterable[Hit], token_for: Callable[[Hit], str] | None = None
) -> str:
    """Return ``text`` with each hit replaced by ``token_for(hit)``.

    Raises ``ValueError`` if a hit does not line up with ``text``, which
    catches hits produced from a different document. Overlapping hits keep
    the earliest start, then the longest span.
    """
    token = token_for or _default_token
    ordered = sorted(hits, key=lambda h: (h.start, -(h.end - h.start)))
    chosen: list[Hit] = []
    cursor = 0
    for hit in ordered:
        if hit.start < 0 or hit.end > len(text) or hit.start >= hit.end:
            raise ValueError(f"hit span {hit.start}:{hit.end} is outside the text")
        if text[hit.start : hit.end] != hit.text:
            raise ValueError(
                f"hit text {hit.text!r} does not match text at {hit.start}:{hit.end}"
            )
        if hit.start < cursor:
            continue
        chosen.append(hit)
        cursor = hit.end
    pieces: list[str] = []
    cursor = 0
    for hit in chosen:
        pieces.append(text[cursor : hit.start])
        pieces.append(token(hit))
        cursor = hit.end
    pieces.append(text[cursor:])
    return "".join(pieces)
