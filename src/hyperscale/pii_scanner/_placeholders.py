"""Turn example placeholder tokens into placeholder patterns."""

from __future__ import annotations

import re
from collections.abc import Iterable

_RUN = re.compile(r"[A-Z]+|[a-z]+|\d+|\s+|.", re.DOTALL)


def _generalise(run: str) -> str:
    if run.isupper():
        return "[A-Z]+"
    if run.islower():
        return "[a-z]+"
    if run.isdigit():
        return r"\d+"
    if run.isspace():
        return r"\s+"
    return re.escape(run)


def placeholder_patterns_from_examples(examples: Iterable[str]) -> list[str]:
    """Build ``placeholder_patterns`` for :func:`scan` from example tokens.

    Each example becomes one pattern of the same shape: a run of capitals,
    lowercase letters, digits or whitespace matches any run of that class, and
    everything else matches literally. ``"MOTHER2FN"`` also matches
    ``"FATHER1SN"``; ``"(LOCAL AUTHORITY)"`` also matches ``"(GP SURGERY)"`` but
    not ``"(SCHOOL1)"``, which needs its own example. Give one example per
    shape. Duplicate shapes collapse; order is kept.

    Raises ``ValueError`` for a blank example.
    """
    if isinstance(examples, str):
        raise TypeError("examples must be an iterable of strings, not a single str")
    patterns: dict[str, None] = {}
    for example in examples:
        if not example.strip():
            raise ValueError(f"blank placeholder example {example!r}")
        body = "".join(_generalise(m.group()) for m in _RUN.finditer(example))
        head = r"(?<!\w)" if re.match(r"\w", example) else ""
        tail = r"(?!\w)" if re.search(r"\w$", example) else ""
        patterns[head + body + tail] = None
    return list(patterns)
