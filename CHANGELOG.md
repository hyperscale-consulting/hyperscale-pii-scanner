# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `scan`, `redact`, `Hit`, `HitKind`, `configure`, `scanner_version`.
- UK recognisers: dates, date of birth, ages, postcodes, National Insurance
  numbers, case references; Presidio's NHS, GB phone, email (offline) and URL
  recognisers.
- GeoNames-derived UK gazetteer reported as `location`.
- Optional `documents` extra with `extract_text` for .docx and .xlsx.
- Vendored `en_core_web_md` 3.8.0; pinned presidio-analyzer 2.2.364 and spaCy 3.8.16.
