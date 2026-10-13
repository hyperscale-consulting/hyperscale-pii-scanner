# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-13

### Added

- `scan(kinds=...)` to limit the kinds reported. An excluded kind cannot hide
  an overlapping hit of a kept kind.
- `placeholder_patterns_from_examples` builds placeholder patterns from example
  tokens, one pattern per shape, as the platform guide describes.

### Changed

- Honorifics (`Mr`, `Mrs`, `Ms`, `Miss`, `Mx`, `Dr`, `Prof`) no longer rescue a
  hit from allowlist or placeholder suppression: `Ms MOTHER2SN` is dropped.
- Model spans that run across a line break are split into one span per line,
  so a header glued to the next line no longer defeats suppression.
- Organisation spans that are an all-caps acronym of six letters or fewer, or
  a whole heading-like line of six words or fewer with no organisation word in
  it, are dropped before overlap resolution. Letterhead lines such as
  `Westfield Medical Practice` are still reported.
- A dotted numeric date (`13.07.2026`) needs a four-digit year, so paragraph
  references such as `6.2.10` are no longer dates. After a date-of-birth label
  a dotted two-digit year (`DOB 14.3.19`) is still accepted.
- Corpus: honorific, heading, acronym and paragraph-reference cases added to
  the expert report; measured organisation precision on the corpus rose from
  0.40 to 0.67 and overall precision from 0.84 to 0.91.
- README documents per-worker memory for multi-process servers.

## [0.1.0] - 2026-10-12

### Added

- `scan`, `redact`, `Hit`, `HitKind`, `configure`, `scanner_version`.
- UK recognisers: dates, date of birth, ages, postcodes, National Insurance
  numbers, case references; Presidio's NHS, GB phone, email (offline) and URL
  recognisers.
- GeoNames-derived UK gazetteer reported as `location`.
- Optional `documents` extra with `extract_text` for .docx and .xlsx.
- Vendored `en_core_web_md` 3.8.0; pinned presidio-analyzer 2.2.364 and spaCy 3.8.16.
