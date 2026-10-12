"""Precision and recall per kind over the fixture corpus, plus timing and memory.

Usage: uv run python scripts/measure.py
"""

from __future__ import annotations

import random
import resource
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hyperscale.pii_scanner import HitKind  # noqa: E402
from hyperscale.pii_scanner import scan  # noqa: E402
from hyperscale.pii_scanner import scanner_version  # noqa: E402
from tests.corpus import Counts  # noqa: E402
from tests.corpus import load_corpus  # noqa: E402
from tests.corpus import score  # noqa: E402

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


def rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return usage / (1024 * 1024) if sys.platform == "darwin" else usage / 1024


def fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def main() -> int:
    totals: dict[HitKind, Counts] = {kind: Counts() for kind in HitKind}
    for doc in load_corpus():
        hits = scan(
            doc.text,
            allowlist=doc.allowlist,
            placeholder_patterns=doc.placeholder_patterns,
        )
        for kind, counts in score(doc, hits).items():
            totals[kind].tp += counts.tp
            totals[kind].fp += counts.fp
            totals[kind].fn += counts.fn
    print("| Kind | TP | FP | FN | Precision | Recall |")
    print("|---|---|---|---|---|---|")
    grand = Counts()
    for kind, c in totals.items():
        if c.tp + c.fp + c.fn == 0:
            continue
        grand.tp += c.tp
        grand.fp += c.fp
        grand.fn += c.fn
        print(
            f"| {kind.value} | {c.tp} | {c.fp} | {c.fn} | "
            f"{fmt(c.precision)} | {fmt(c.recall)} |"
        )
    print(
        f"| all | {grand.tp} | {grand.fp} | {grand.fn} | "
        f"{fmt(grand.precision)} | {fmt(grand.recall)} |"
    )
    print()
    loaded_rss = rss_mb()
    text = perf_document()
    scan(text[:2000])  # warm
    started = time.perf_counter()
    hits = scan(text)
    elapsed = time.perf_counter() - started
    print(
        f"Perf document: {len(text.split())} words, {len(hits)} hits, {elapsed:.2f} s"
    )
    print(
        f"Resident memory after load: {loaded_rss:.0f} MB; "
        f"peak after scan: {rss_mb():.0f} MB"
    )
    print(f"Versions: {scanner_version()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
