from collections import Counter

import pytest

from hyperscale.pii_scanner import scan
from tests.corpus import CorpusDocument
from tests.corpus import load_corpus

DOCS = load_corpus()


@pytest.mark.parametrize("doc", DOCS, ids=[d.name for d in DOCS])
def test_every_planted_identifier_is_found(doc: CorpusDocument):
    hits = scan(
        doc.text, allowlist=doc.allowlist, placeholder_patterns=doc.placeholder_patterns
    )
    found = Counter((h.kind, h.text) for h in hits)
    missing = [key for key, n in Counter(doc.expected).items() if found[key] < n]
    assert not missing, (
        f"missing in {doc.name}: {missing}; "
        f"hits were {[(h.kind.value, h.text) for h in hits]}"
    )


@pytest.mark.parametrize("doc", DOCS, ids=[d.name for d in DOCS])
def test_no_placeholder_or_allowlisted_text_is_reported(doc: CorpusDocument):
    hits = scan(
        doc.text, allowlist=doc.allowlist, placeholder_patterns=doc.placeholder_patterns
    )
    forbidden_spans = [
        (start, start + len(item))
        for item in doc.must_not_report
        for start in _occurrences(doc.text, item)
    ]
    leaked = [
        (h.kind.value, h.text)
        for h in hits
        if any(start <= h.start and h.end <= end for start, end in forbidden_spans)
    ]
    assert leaked == []


def _occurrences(text: str, needle: str) -> list[int]:
    starts: list[int] = []
    position = text.find(needle)
    while position != -1:
        starts.append(position)
        position = text.find(needle, position + 1)
    return starts


def test_corpus_has_the_required_documents():
    names = {d.name for d in DOCS}
    assert {
        "expert_report",
        "clinical_letter",
        "case_note",
        "business_letter",
        "placeholders_only",
    } <= names
