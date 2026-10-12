"""Whole-word, case-sensitive matching of the shipped UK place-name list."""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import cache
from importlib.resources import files

_TOKEN = re.compile(r"(?<![\w'’])[A-Z]\w*")
_FIRST_WORD = re.compile(r"\w+")


class PlaceIndex:
    """Index names by their first token so a scan is linear in the text length."""

    def __init__(self, names: Iterable[str]) -> None:
        self.names: frozenset[str] = frozenset(n.strip() for n in names if n.strip())
        by_first: dict[str, list[str]] = {}
        for name in self.names:
            first = _FIRST_WORD.match(name)
            if first is None:
                continue
            by_first.setdefault(first.group(), []).append(name)
        for candidates in by_first.values():
            candidates.sort(key=len, reverse=True)
        self._by_first = by_first

    @staticmethod
    def _boundary(text: str, end: int) -> bool:
        return end == len(text) or not (text[end].isalnum() or text[end] == "_")

    def find(self, text: str) -> list[tuple[int, int]]:
        spans: list[tuple[int, int]] = []
        cursor = 0
        for match in _TOKEN.finditer(text):
            if match.start() < cursor:
                continue
            candidates = self._by_first.get(match.group())
            if candidates is None:
                continue
            for name in candidates:
                end = match.start() + len(name)
                if text.startswith(name, match.start()) and self._boundary(text, end):
                    spans.append((match.start(), end))
                    cursor = end
                    break
        return spans


@cache
def load_places() -> PlaceIndex:
    data = (
        files("hyperscale.pii_scanner")
        .joinpath("data/uk_places.txt")
        .read_text(encoding="utf-8")
    )
    return PlaceIndex(
        line for line in data.splitlines() if line and not line.startswith("#")
    )
