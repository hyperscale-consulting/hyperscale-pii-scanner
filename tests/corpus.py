"""Shared corpus loading and scoring for the corpus test and scripts/measure.py."""

from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from hyperscale.pii_scanner import Hit
from hyperscale.pii_scanner import HitKind

CORPUS_DIR = Path(__file__).resolve().parent / "fixtures" / "corpus"


@dataclass(frozen=True)
class CorpusDocument:
    name: str
    text: str
    allowlist: list[str]
    placeholder_patterns: list[str]
    expected: list[tuple[HitKind, str]]
    must_not_report: list[str]


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float | None:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else None

    @property
    def recall(self) -> float | None:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None


def load_corpus() -> list[CorpusDocument]:
    docs: list[CorpusDocument] = []
    for text_path in sorted(CORPUS_DIR.glob("*.txt")):
        sidecar_path = text_path.with_suffix(".expected.json")
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        docs.append(
            CorpusDocument(
                name=text_path.stem,
                text=text_path.read_text(encoding="utf-8"),
                allowlist=list(sidecar.get("allowlist", [])),
                placeholder_patterns=list(sidecar.get("placeholder_patterns", [])),
                expected=[
                    (HitKind(e["kind"]), e["text"]) for e in sidecar.get("expected", [])
                ],
                must_not_report=list(sidecar.get("must_not_report", [])),
            )
        )
    return docs


def score(doc: CorpusDocument, hits: list[Hit]) -> dict[HitKind, Counts]:
    """Match hits to expected entries by (kind, text) as multisets."""
    expected = Counter(doc.expected)
    found = Counter((h.kind, h.text) for h in hits)
    counts: dict[HitKind, Counts] = {kind: Counts() for kind in HitKind}
    for key in set(expected) | set(found):
        kind = key[0]
        matched = min(expected[key], found[key])
        counts[kind].tp += matched
        counts[kind].fp += found[key] - matched
        counts[kind].fn += expected[key] - matched
    return counts


WORDS = (
    "the mother reported that the child attended school regularly and the social "
    "worker visited the family home on several occasions during the assessment "
    "period while the father maintained that contact had been positive and the "
    "guardian agreed"
).split()


def perf_document(words: int = 15000, seed: int = 1) -> str:
    rng = random.Random(seed)
    paragraphs: list[str] = []
    total = 0
    while total < words:
        body = " ".join(rng.choice(WORDS) for _ in range(110)).capitalize()
        paragraphs.append(
            f"{body}. The review on 13th of July 2026 in Leeds was attended by "
            "Dr Smith, NHS number 943 476 5919, postcode LS1 4AP, "
            "phone 0113 496 0000, aged 34."
        )
        total += 130
    return "\n\n".join(paragraphs)
