"""Presidio's email recogniser with the public-suffix lookup pinned offline."""

from __future__ import annotations

import tldextract
from presidio_analyzer.predefined_recognizers import EmailRecognizer

# No suffix-list URLs and no cache directory: the bundled snapshot is the only source.
_EXTRACT = tldextract.TLDExtract(
    suffix_list_urls=(), cache_dir=None, fallback_to_snapshot=True
)


class OfflineEmailRecognizer(EmailRecognizer):
    def __init__(self) -> None:
        super().__init__(name="OfflineEmailRecognizer")

    def validate_result(self, pattern_text: str) -> bool:
        return _EXTRACT(pattern_text).fqdn != ""
