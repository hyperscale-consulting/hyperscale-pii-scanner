import threading
from concurrent.futures import ThreadPoolExecutor

from hyperscale.pii_scanner import Hit
from hyperscale.pii_scanner import scan
from tests.corpus import load_corpus


def test_concurrent_scans_match_serial_results():
    docs = load_corpus() * 2
    serial = [
        scan(d.text, allowlist=d.allowlist, placeholder_patterns=d.placeholder_patterns)
        for d in docs
    ]
    barrier = threading.Barrier(len(docs))

    def work(index: int) -> list[Hit]:
        barrier.wait()
        d = docs[index]
        return scan(
            d.text, allowlist=d.allowlist, placeholder_patterns=d.placeholder_patterns
        )

    with ThreadPoolExecutor(max_workers=len(docs)) as pool:
        concurrent = list(pool.map(work, range(len(docs))))
    assert concurrent == serial
