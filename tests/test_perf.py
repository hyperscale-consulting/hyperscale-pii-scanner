import os
import time

import pytest

from hyperscale.pii_scanner import scan
from tests.corpus import perf_document

BUDGET = float(os.environ.get("PII_SCANNER_PERF_BUDGET_SECONDS", "5"))


@pytest.mark.perf
def test_fifteen_thousand_words_scan_within_budget():
    text = perf_document()
    assert len(text.split()) >= 15000
    scan(text[:3000])  # warm-up after the session fixture loaded the model
    started = time.perf_counter()
    hits = scan(text)
    elapsed = time.perf_counter() - started
    assert hits
    assert elapsed < BUDGET, f"scan took {elapsed:.2f}s, budget {BUDGET}s"
