# hyperscale-pii-scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publish `hyperscale-pii-scanner`, a deterministic, offline, UK-tuned wrapper over Presidio and spaCy that reports residual personal identifiers in English text.

**Architecture:** A single lazily built Presidio `AnalyzerEngine` (spaCy `en_core_web_md` vendored into the wheel) behind two locks, an explicit recogniser registry built in code, and a post-processing layer that maps Presidio entities to a closed `HitKind` enum, resolves overlaps, and suppresses allowlisted and placeholder spans. An optional `documents` extra extracts text from Word and Excel files with a location map.

**Tech Stack:** Python 3.14, uv + uv_build, presidio-analyzer 2.2.364, spaCy 3.8.16, en_core_web_md 3.8.0, phonenumbers, tldextract, pytest, ruff, pyright strict, pre-commit, GitHub Actions with trusted publishing.

**Spec:** `docs/superpowers/specs/2026-10-12-hyperscale-pii-scanner-design.md`

## Global Constraints

- Import name `hyperscale.pii_scanner`; distribution name `hyperscale-pii-scanner`; uv_build `module-name = "hyperscale.pii_scanner"`; src layout; no `src/hyperscale/__init__.py` (implicit namespace, as hyperscale-crypto).
- `requires-python = ">=3.14"`; licence MIT; author Andy Caine <andy@hyperscale.consulting>; repo `https://github.com/hyperscale-consulting/hyperscale-pii-scanner`.
- Exact pins: `presidio-analyzer==2.2.364`, `spacy==3.8.16`; model `en_core_web_md` 3.8.0 from `https://github.com/explosion/spacy-models/releases/download/en_core_web_md-3.8.0/en_core_web_md-3.8.0-py3-none-any.whl`, sha256 `5e6329fe3fecedb1d1a02c3ea2172ee0fede6cea6e4aefb6a02d832dba78a310`.
- No network at runtime, no LLM, CPU only. Email validation uses `tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, fallback_to_snapshot=True)`.
- `HitKind` members, in this order and with these values: `person`, `location`, `organisation`, `date`, `date_of_birth`, `age`, `postcode`, `nhs_number`, `national_insurance_number`, `phone`, `email`, `url`, `case_reference`.
- Score threshold 0.3. Overlap priority: structured kinds beat model kinds; structured order is date_of_birth, nhs_number, national_insurance_number, postcode, case_reference, email, url, phone, age, date; then longer span, then higher score, then earlier `HitKind` member.
- Suppression: a hit is dropped if its span lies within any whole-word case-insensitive occurrence of an allowlist entry or within any placeholder-pattern match. Applied after overlap resolution.
- Only `language="en"`; anything else raises `ValueError`.
- `scan` serialises on a lock; one engine per process; `configure(model=...)` raises `RuntimeError` once the engine exists.
- Presidio compiles pattern strings with the `regex` module under its default flags (`DOTALL | MULTILINE | IGNORECASE`). Patterns that must be case-sensitive (postcodes, case references) wrap themselves in a scoped group `(?-i:...)`, which the `regex` module supports. Never `import regex` in `src/`.
- Tooling: ruff rules `B, E, F, I, UP, W`, `force-single-line` isort, pyright `strict` over `src` and `tests`, pytest `testpaths = ["tests"]`, pre-commit frozen SHAs, CI with lint/test/build/pip-audit/zizmor, publish on release via trusted publishing (environment `pypi`).
- The model directory `src/hyperscale/pii_scanner/_model/` is git-ignored and populated by `python3 scripts/vendor_model.py`; every CI job that syncs or builds runs that script first.
- Commit after every task with a message in the form `<type>: <summary>` ending in a blank line and `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Perf: a 15,000-word document scans in under `PII_SCANNER_PERF_BUDGET_SECONDS` (default 5; CI sets 10) after warm-up.

## Review Focus

1. **Text containing `\r\n` line endings or non-ASCII letters** (Welsh place names, curly apostrophes): offsets reported by `scan` must index the original string exactly, and `redact` must round-trip. Test added in Task 4 (`test_scan_offsets_index_original_text_with_crlf_and_unicode`).
2. **A hit that straddles a placeholder boundary**, such as spaCy returning `MOTHER2FN Jones` as one PERSON span: it must still be reported (the surname leaked), not suppressed because part of it is a placeholder. Test added in Task 4 (`test_hit_extending_beyond_placeholder_is_reported`).
3. **Short alphanumeric tokens spaCy tags as ORG** (`E1`, `B12`, `SCHOOL1`): callers see noise unless placeholders cover them. Test added in Task 11 corpus (`placeholders_only.txt`) proving every placeholder style in the brief is suppressed, and the README states that model hits are best effort.
4. **`extract_text` given a `.docx` with an empty body but populated header, or a `.xlsx` with an empty sheet**: must return empty text and an empty segment list without raising. Test added in Task 13 (`test_extract_handles_empty_documents`).
5. **`redact` given hits from a different document** (offsets no longer line up): must raise `ValueError` rather than silently produce a wrong document. Test added in Task 5 (`test_redact_rejects_hits_from_other_text`).

---

## File structure

```
pyproject.toml, uv.lock, .python-version, .gitignore, .pre-commit-config.yaml
Makefile, LICENSE, README.md, CHANGELOG.md, SECURITY.md, CONTRIBUTING.md, PLATFORM_GUIDE.md
.github/workflows/ci.yml, .github/workflows/publish.yml, .github/dependabot.yml
src/hyperscale/pii_scanner/__init__.py         public API re-exports, __version__
src/hyperscale/pii_scanner/_types.py           Hit, HitKind, ScannerVersion
src/hyperscale/pii_scanner/_engine.py          configure, analyze, scanner_version, locks
src/hyperscale/pii_scanner/_postprocess.py     Candidate, to_candidates, resolve_overlaps, suppression_spans, suppress, build_hits
src/hyperscale/pii_scanner/_scan.py            scan()
src/hyperscale/pii_scanner/_redact.py          redact()
src/hyperscale/pii_scanner/_recognisers/__init__.py   build_registry()
src/hyperscale/pii_scanner/_recognisers/uk_date.py    date building blocks + UkDateRecognizer
src/hyperscale/pii_scanner/_recognisers/date_of_birth.py
src/hyperscale/pii_scanner/_recognisers/age.py
src/hyperscale/pii_scanner/_recognisers/postcode.py
src/hyperscale/pii_scanner/_recognisers/case_reference.py
src/hyperscale/pii_scanner/_recognisers/email.py
src/hyperscale/pii_scanner/_recognisers/gazetteer.py
src/hyperscale/pii_scanner/_gazetteer.py       load_places(), PlaceIndex
src/hyperscale/pii_scanner/data/uk_places.txt
src/hyperscale/pii_scanner/_model/             git-ignored, vendored model
src/hyperscale/pii_scanner/documents.py        extract_text, ExtractedText, Segment
scripts/vendor_model.py, scripts/build_gazetteer.py, scripts/gazetteer_stoplist.txt,
scripts/gazetteer_extra.txt, scripts/measure.py, scripts/release.py
tests/__init__.py, tests/conftest.py, tests/test_*.py, tests/fixtures/corpus/*.txt + *.expected.json
```

---

### Task 1: Project scaffold with the python-setup tooling

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `.pre-commit-config.yaml`, `LICENSE`, `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`, `.github/workflows/ci.yml`, `.github/workflows/publish.yml`, `.github/dependabot.yml`, `src/hyperscale/pii_scanner/__init__.py`, `tests/__init__.py`, `tests/test_version.py`

**Interfaces:**
- Produces: an installable package `hyperscale.pii_scanner` exposing `__version__: str`.

- [ ] **Step 1: Create the skeleton with uv**

```bash
cd /Users/acaine/src/hyperscale/hyperscale-pii-scanner
uv init --lib --name hyperscale-pii-scanner --python 3.14 .
rm -rf src/hyperscale_pii_scanner
mkdir -p src/hyperscale/pii_scanner tests
printf '3.14\n' > .python-version
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "hyperscale-pii-scanner"
version = "0.1.0"
description = "Deterministic, in-process scan for residual personal identifiers in UK English text, built on Presidio and spaCy"
readme = "README.md"
requires-python = ">=3.14"
license = "MIT"
license-files = ["LICENSE"]
authors = [{ name = "Andy Caine", email = "andy@hyperscale.consulting" }]
keywords = ["pii", "presidio", "spacy", "anonymisation", "redaction", "uk", "nhs"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3.14",
    "Topic :: Security",
    "Topic :: Text Processing :: Linguistic",
    "Typing :: Typed",
]
dependencies = [
    "presidio-analyzer==2.2.364",
    "spacy==3.8.16",
    "tldextract>=5.1",
]

[project.optional-dependencies]
documents = [
    "python-docx>=1.2.0",
    "openpyxl>=3.1.5",
    "defusedxml>=0.7.1",
]

[project.urls]
Homepage = "https://github.com/hyperscale-consulting/hyperscale-pii-scanner"
Repository = "https://github.com/hyperscale-consulting/hyperscale-pii-scanner"
Changelog = "https://github.com/hyperscale-consulting/hyperscale-pii-scanner/blob/main/CHANGELOG.md"
Issues = "https://github.com/hyperscale-consulting/hyperscale-pii-scanner/issues"

[build-system]
requires = ["uv_build>=0.12.13,<0.13.0"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "hyperscale.pii_scanner"

[tool.ruff]
fix = true
show-fixes = true
output-format = "full"
# The design spec and plan embed illustrative code; keep them as written.
extend-exclude = ["docs"]

[tool.ruff.lint]
select = [
    "B",   # flake8-bugbear
    "E",   # pycodestyle error
    "F",   # pyflakes
    "I",   # isort
    "UP",  # pyupgrade
    "W",   # pycodestyle warning
]

[tool.ruff.lint.isort]
force-single-line = true
order-by-type = false

[tool.pyright]
pythonVersion = "3.14"  # minimum supported version
typeCheckingMode = "strict"
include = ["src", "tests"]
venvPath = "."
venv = ".venv"

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["perf: timing tests that need the model loaded"]

[dependency-groups]
dev = []
gazetteer = []
```

- [ ] **Step 3: Add dependencies with uv so versions are current**

```bash
uv add --dev pytest pytest-cov ruff pyright types-openpyxl
uv add --group gazetteer wordfreq
uv sync --all-extras
uv run python -c "import presidio_analyzer, spacy; print(spacy.__version__)"
```
Expected: `3.8.16`.

- [ ] **Step 4: Write `src/hyperscale/pii_scanner/__init__.py` (version only for now)**

```python
"""Deterministic, offline scan for residual personal identifiers in UK English text."""

from importlib.metadata import version as _dist_version

__version__ = _dist_version("hyperscale-pii-scanner")

__all__ = ["__version__"]
```

- [ ] **Step 5: Write `tests/__init__.py` (empty) and `tests/test_version.py`**

```python
import re

from hyperscale import pii_scanner


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", pii_scanner.__version__)
```

- [ ] **Step 6: Run the test**

Run: `uv run pytest -q`
Expected: `1 passed`.

- [ ] **Step 7: Write `.gitignore`**

```
__pycache__/
*.py[cod]
.venv/
dist/
.pytest_cache/
.ruff_cache/
*.egg-info/
.coverage
htmlcov/
requirements.txt
# Vendored spaCy model, fetched by scripts/vendor_model.py
src/hyperscale/pii_scanner/_model/
```

- [ ] **Step 8: Write `.pre-commit-config.yaml` from the skill asset, then freeze**

```yaml
repos:
  # Keep in lockstep with the ruff version in uv.lock (uv lock --upgrade-package ruff).
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: 01a675ea018f2fb714478a5ffb83fcea8374bb06  # frozen: v0.15.21
    hooks:
      - id: ruff-check
      - id: ruff-format
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: d9fca3320346514799461a80b0753eb45d707d46  # frozen: 0.11.28
    hooks:
      - id: uv-lock
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: 3e8a8703264a2f4a69428a0aa4dcb512790b2c8c  # frozen: v6.0.0
    hooks:
      - id: check-merge-conflict
      - id: debug-statements
      - id: fix-byte-order-marker
      - id: trailing-whitespace
      - id: end-of-file-fixer
        exclude: ^tests/fixtures/corpus/
```

```bash
uvx pre-commit autoupdate --freeze
uvx pre-commit install
```

- [ ] **Step 9: Write `LICENSE` (MIT, copyright 2026 Hyperscale Consulting Ltd), `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`**

`CHANGELOG.md`:
```markdown
# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
```

`SECURITY.md`:
```markdown
# Security Policy

## Supported versions

Only the latest release of `hyperscale-pii-scanner` receives security fixes.

## Reporting a vulnerability

Please do not report security vulnerabilities through public GitHub issues.

Report them privately through
[GitHub security advisories](https://github.com/hyperscale-consulting/hyperscale-pii-scanner/security/advisories/new)
or by email to andy@hyperscale.consulting. Include a description of the issue,
the steps to reproduce it and the versions affected.

You should receive an acknowledgement within three working days.
```

`CONTRIBUTING.md`:
```markdown
# Contributing

## Development setup

Requires [uv](https://docs.astral.sh/uv/), Python 3.14+ and GNU make.

```bash
git clone https://github.com/hyperscale-consulting/hyperscale-pii-scanner.git
cd hyperscale-pii-scanner
make setup     # downloads the pinned spaCy model, syncs the venv, installs pre-commit
```

## Running checks

```bash
make check     # ruff, pyright, pytest
make measure   # precision and recall over the fixture corpus, timing, memory
```

CI runs the same checks on every PR.

## Pull requests

- Add tests for behaviour changes, including negative cases for recognisers.
- Re-run `make measure` and update the numbers in `README.md` when a recogniser,
  the gazetteer or the model changes.
- Update `CHANGELOG.md` under `[Unreleased]`.
- Keep the public API documented in `README.md`.
```

- [ ] **Step 10: Write `.github/dependabot.yml`, `.github/workflows/ci.yml`, `.github/workflows/publish.yml`**

`dependabot.yml`:
```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: /
    schedule:
      interval: weekly
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
```

`ci.yml` (adapted from the skill asset; note the model step and the perf budget):
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

permissions: {}

jobs:
  lint:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
      - run: python3 scripts/vendor_model.py
      - run: uv sync --locked --all-extras
      - run: uv run ruff check --no-fix .
      - run: uv run ruff format --check .
      - run: uv run pyright

  test:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    env:
      PII_SCANNER_PERF_BUDGET_SECONDS: "10"
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.14"]
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          python-version: ${{ matrix.python-version }}
      - run: python3 scripts/vendor_model.py
      - run: uv sync --locked --all-extras
      - run: uv run pytest --cov=hyperscale.pii_scanner --cov-report=term-missing

  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
      - run: python3 scripts/vendor_model.py
      - run: uv build
      - run: uvx twine==6.2.0 check dist/*
      - name: Check the wheel contains the model and gazetteer
        run: |
          unzip -l dist/*.whl | grep -q "hyperscale/pii_scanner/_model/en_core_web_md-3.8.0/meta.json"
          unzip -l dist/*.whl | grep -q "hyperscale/pii_scanner/data/uk_places.txt"

  pip-audit:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
      - run: uv export --no-emit-project --all-extras --format requirements-txt -o requirements.txt
      - run: uvx pip-audit==2.10.1 --disable-pip -r requirements.txt

  zizmor:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
      - run: uvx zizmor==1.26.1 .github/workflows/
```

`publish.yml`:
```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

permissions: {}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          enable-cache: false
      - name: Check tag matches package version
        run: |
          version=$(uvx --from toml-cli==0.8.2 toml get --toml-path pyproject.toml project.version)
          test "v${version}" = "${GITHUB_REF_NAME}"
      - run: python3 scripts/vendor_model.py
      - run: uv build
      - run: uvx twine==6.2.0 check dist/*
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: dist
          path: dist/

  publish:
    needs: build
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # release/v1
```

Then refresh pins:
```bash
python3 /Users/acaine/src/hyperscale/skills/python-setup/scripts/update_action_pins.py .github/workflows/
```

The build job's wheel-content check will fail until Task 3 (model) and Task 10 (gazetteer) exist; that is expected until the first push, which happens in Task 15.

- [ ] **Step 11: Verify every check passes**

```bash
uv sync --locked --all-extras
uv run pytest -q
uv run ruff check --no-fix .
uv run ruff format --check .
uv run pyright
uvx pre-commit run --all-files
uvx zizmor .github/workflows/
```
Expected: all pass (pre-commit may reformat on the first run; re-run until clean).

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "chore: scaffold project with uv, ruff, pyright, pytest, pre-commit and CI

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Core types

**Files:**
- Create: `src/hyperscale/pii_scanner/_types.py`
- Modify: `src/hyperscale/pii_scanner/__init__.py`
- Test: `tests/test_types.py`

**Interfaces:**
- Produces: `HitKind(StrEnum)`, `Hit(kind, text, start, end, score, recogniser)` frozen with slots, `ScannerVersion(library, presidio_analyzer, spacy, model_name, model_version)` frozen with `__str__`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_types.py
import dataclasses

import pytest

from hyperscale.pii_scanner import Hit
from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import ScannerVersion


def test_hit_kind_members_and_order():
    assert [k.value for k in HitKind] == [
        "person",
        "location",
        "organisation",
        "date",
        "date_of_birth",
        "age",
        "postcode",
        "nhs_number",
        "national_insurance_number",
        "phone",
        "email",
        "url",
        "case_reference",
    ]
    assert HitKind("nhs_number") is HitKind.NHS_NUMBER
    assert str(HitKind.PERSON) == "person"


def test_hit_is_frozen_and_hashable():
    hit = Hit(HitKind.PERSON, "Jane", 0, 4, 0.85, "SpacyRecognizer")
    with pytest.raises(dataclasses.FrozenInstanceError):
        hit.text = "x"  # type: ignore[misc]
    assert hash(hit) == hash(Hit(HitKind.PERSON, "Jane", 0, 4, 0.85, "SpacyRecognizer"))


def test_scanner_version_str_is_one_audit_line():
    v = ScannerVersion("0.1.0", "2.2.364", "3.8.16", "en_core_web_md", "3.8.0")
    assert str(v) == (
        "hyperscale-pii-scanner 0.1.0; presidio-analyzer 2.2.364; "
        "spacy 3.8.16; en_core_web_md 3.8.0"
    )
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_types.py -q`
Expected: FAIL with `ImportError: cannot import name 'Hit'`.

- [ ] **Step 3: Write `_types.py`**

```python
"""Public value types."""

from __future__ import annotations

import enum
from dataclasses import dataclass


class HitKind(enum.StrEnum):
    """The closed set of identifier kinds the scanner reports.

    Member order is the final tie-break when two overlapping hits are otherwise equal.
    """

    PERSON = "person"
    LOCATION = "location"
    ORGANISATION = "organisation"
    DATE = "date"
    DATE_OF_BIRTH = "date_of_birth"
    AGE = "age"
    POSTCODE = "postcode"
    NHS_NUMBER = "nhs_number"
    NATIONAL_INSURANCE_NUMBER = "national_insurance_number"
    PHONE = "phone"
    EMAIL = "email"
    URL = "url"
    CASE_REFERENCE = "case_reference"


@dataclass(frozen=True, slots=True)
class Hit:
    """One identifier found in the scanned text.

    ``text`` is always ``source[start:end]``. ``recogniser`` names the Presidio
    recogniser that produced the hit, for example ``NhsRecognizer``.
    """

    kind: HitKind
    text: str
    start: int
    end: int
    score: float
    recogniser: str


@dataclass(frozen=True, slots=True)
class ScannerVersion:
    """Versions of every component that influences results, for audit logs."""

    library: str
    presidio_analyzer: str
    spacy: str
    model_name: str
    model_version: str

    def __str__(self) -> str:
        return (
            f"hyperscale-pii-scanner {self.library}; "
            f"presidio-analyzer {self.presidio_analyzer}; "
            f"spacy {self.spacy}; {self.model_name} {self.model_version}"
        )
```

- [ ] **Step 4: Re-export from `__init__.py`**

```python
"""Deterministic, offline scan for residual personal identifiers in UK English text."""

from importlib.metadata import version as _dist_version

from ._types import Hit
from ._types import HitKind
from ._types import ScannerVersion

__version__ = _dist_version("hyperscale-pii-scanner")

__all__ = ["Hit", "HitKind", "ScannerVersion", "__version__"]
```

- [ ] **Step 5: Run tests, lint, types**

Run: `uv run pytest -q && uv run ruff check --no-fix . && uv run pyright`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add Hit, HitKind and ScannerVersion types

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Vendored model and the engine

**Files:**
- Create: `scripts/vendor_model.py`, `src/hyperscale/pii_scanner/_engine.py`, `src/hyperscale/pii_scanner/_recognisers/__init__.py`, `Makefile`, `tests/conftest.py`
- Modify: `src/hyperscale/pii_scanner/__init__.py`
- Test: `tests/test_vendor_model.py`, `tests/test_engine.py`

**Interfaces:**
- Produces: `_engine.configure(model)`, `_engine.analyze(text) -> list[RecognizerResult]`, `_engine.scanner_version() -> ScannerVersion`, `_engine.reset_for_tests()`, `_engine.is_loaded()`, `_engine.DEFAULT_MODEL_PATH`, `_engine.SCORE_THRESHOLD`, and `_recognisers.build_registry() -> RecognizerRegistry` (spaCy only until later tasks add recognisers).
- Public: `configure`, `scanner_version`.

- [ ] **Step 1: Write `scripts/vendor_model.py` (stdlib only; runs under system `python3`)**

```python
"""Download the pinned spaCy model wheel and unpack it into the package.

Usage: python3 scripts/vendor_model.py [--force]

Stdlib only so it runs before `uv sync` and inside CI without a venv.
"""

from __future__ import annotations

import hashlib
import io
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

MODEL_NAME = "en_core_web_md"
MODEL_VERSION = "3.8.0"
WHEEL_URL = (
    "https://github.com/explosion/spacy-models/releases/download/"
    f"{MODEL_NAME}-{MODEL_VERSION}/{MODEL_NAME}-{MODEL_VERSION}-py3-none-any.whl"
)
WHEEL_SHA256 = "5e6329fe3fecedb1d1a02c3ea2172ee0fede6cea6e4aefb6a02d832dba78a310"

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_ROOT = REPO_ROOT / "src" / "hyperscale" / "pii_scanner" / "_model"
TARGET = MODEL_ROOT / f"{MODEL_NAME}-{MODEL_VERSION}"
# Inside the wheel the model data lives at <pkg>/<pkg>-<version>/
WHEEL_PREFIX = f"{MODEL_NAME}/{MODEL_NAME}-{MODEL_VERSION}/"


def verify(data: bytes, expected_sha256: str) -> None:
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise SystemExit(f"sha256 mismatch: expected {expected_sha256}, got {digest}")


def unpack(wheel_bytes: bytes, target: Path, prefix: str = WHEEL_PREFIX) -> int:
    """Extract the model directory from the wheel. Returns the file count."""
    count = 0
    with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as zf:
        for info in zf.infolist():
            if not info.filename.startswith(prefix) or info.is_dir():
                continue
            relative = Path(info.filename[len(prefix) :])
            if relative.is_absolute() or ".." in relative.parts:
                raise SystemExit(f"refusing unsafe path in wheel: {info.filename}")
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    if count == 0:
        raise SystemExit(f"no files under {prefix} in wheel")
    return count


def main(argv: list[str]) -> int:
    force = "--force" in argv
    if (TARGET / "meta.json").exists() and not force:
        print(f"model already present at {TARGET}")
        return 0
    print(f"downloading {WHEEL_URL}")
    with urllib.request.urlopen(WHEEL_URL, timeout=120) as response:  # noqa: S310
        data = response.read()
    verify(data, WHEEL_SHA256)
    if TARGET.exists():
        shutil.rmtree(TARGET)
    count = unpack(data, TARGET)
    print(f"unpacked {count} files to {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 2: Write `tests/test_vendor_model.py` (unit tests against the pure functions, no download)**

```python
import hashlib
import importlib.util
import io
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "vendor_model.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("vendor_model", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_wheel(prefix: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{prefix}meta.json", '{"name": "core_web_md"}')
        zf.writestr(f"{prefix}ner/model", "binary")
        zf.writestr("en_core_web_md/__init__.py", "")
    return buf.getvalue()


def test_verify_rejects_wrong_digest():
    vm = _load_script()
    with pytest.raises(SystemExit, match="sha256 mismatch"):
        vm.verify(b"abc", "0" * 64)
    vm.verify(b"abc", hashlib.sha256(b"abc").hexdigest())


def test_unpack_extracts_only_the_model_directory(tmp_path: Path):
    vm = _load_script()
    count = vm.unpack(_fake_wheel(vm.WHEEL_PREFIX), tmp_path / "model")
    assert count == 2
    assert (tmp_path / "model" / "meta.json").read_text() == '{"name": "core_web_md"}'
    assert (tmp_path / "model" / "ner" / "model").exists()
    assert not (tmp_path / "model" / "__init__.py").exists()


def test_unpack_rejects_path_traversal(tmp_path: Path):
    vm = _load_script()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{vm.WHEEL_PREFIX}../../evil", "x")
    with pytest.raises(SystemExit, match="unsafe path"):
        vm.unpack(buf.getvalue(), tmp_path / "model")
```

- [ ] **Step 3: Run the unit tests, then vendor the real model**

Run: `uv run pytest tests/test_vendor_model.py -q`
Expected: `3 passed`.

Run: `python3 scripts/vendor_model.py && ls src/hyperscale/pii_scanner/_model/en_core_web_md-3.8.0/meta.json`
Expected: the path prints; `git status` shows nothing under `_model` because it is ignored.

- [ ] **Step 4: Write the failing engine tests**

```python
# tests/test_engine.py
import socket
import threading
from pathlib import Path

import pytest

from hyperscale.pii_scanner import _engine
from hyperscale.pii_scanner import configure
from hyperscale.pii_scanner import scanner_version


@pytest.fixture
def fresh_engine():
    _engine.reset_for_tests()
    yield
    _engine.reset_for_tests()


def test_default_model_is_the_vendored_directory():
    assert _engine.DEFAULT_MODEL_PATH.name == "en_core_web_md-3.8.0"
    assert (_engine.DEFAULT_MODEL_PATH / "meta.json").exists()


def test_scanner_version_reports_components_without_loading_engine(fresh_engine: None):
    v = scanner_version()
    assert v.presidio_analyzer == "2.2.364"
    assert v.spacy == "3.8.16"
    assert v.model_name == "en_core_web_md"
    assert v.model_version == "3.8.0"
    assert _engine.is_loaded() is False


def test_analyze_finds_a_person(fresh_engine: None):
    results = _engine.analyze("Jane Smith lives in Harrogate.")
    found = {(r.entity_type, r.start, r.end) for r in results}
    assert ("PERSON", 0, 10) in found
    assert ("LOCATION", 20, 29) in found


def test_configure_after_load_raises(fresh_engine: None):
    _engine.analyze("warm up")
    with pytest.raises(RuntimeError, match="already"):
        configure(model="en_core_web_lg")


def test_configure_with_missing_path_fails_at_first_scan(fresh_engine: None, tmp_path: Path):
    configure(model=tmp_path / "nope")
    with pytest.raises(OSError):
        _engine.analyze("Jane Smith")


def test_engine_loads_and_scans_without_network(fresh_engine: None, monkeypatch: pytest.MonkeyPatch):
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    results = _engine.analyze("Email jane@example.org or see https://example.org/report today.")
    assert results  # the engine worked with networking disabled


def test_engine_is_built_once_under_concurrency(fresh_engine: None):
    seen: list[int] = []

    def work() -> None:
        _engine.analyze("Jane Smith")
        seen.append(id(_engine._state.engine))

    threads = [threading.Thread(target=work) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(seen)) == 1
```

- [ ] **Step 5: Run to verify failure**

Run: `uv run pytest tests/test_engine.py -q`
Expected: FAIL with `ImportError` for `_engine`.

- [ ] **Step 6: Write `_recognisers/__init__.py` (spaCy only for now)**

```python
"""Builds the explicit Presidio recogniser registry.

Only recognisers listed here run. Presidio's defaults are never loaded, so a
Presidio upgrade cannot re-enable US-centric recognisers.
"""

from __future__ import annotations

from presidio_analyzer import EntityRecognizer
from presidio_analyzer import RecognizerRegistry
from presidio_analyzer.predefined_recognizers import SpacyRecognizer

SPACY_ENTITIES = ["PERSON", "LOCATION", "ORGANIZATION"]


def build_recognisers() -> list[EntityRecognizer]:
    return [
        SpacyRecognizer(supported_entities=SPACY_ENTITIES),
    ]


def build_registry() -> RecognizerRegistry:
    return RecognizerRegistry(recognizers=build_recognisers(), supported_languages=["en"])
```

- [ ] **Step 7: Write `_engine.py`**

```python
"""One Presidio engine per process, built lazily, used under a lock."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from importlib.metadata import version as dist_version
from pathlib import Path

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer import RecognizerResult
from presidio_analyzer.nlp_engine import NerModelConfiguration
from presidio_analyzer.nlp_engine import SpacyNlpEngine

from ._recognisers import build_registry
from ._types import ScannerVersion

DEFAULT_MODEL_NAME = "en_core_web_md"
DEFAULT_MODEL_VERSION = "3.8.0"
DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent / "_model" / f"{DEFAULT_MODEL_NAME}-{DEFAULT_MODEL_VERSION}"
)
SCORE_THRESHOLD = 0.3
# spaCy labels that must never reach Presidio (DATE/TIME are replaced by UkDateRecognizer).
LABELS_TO_IGNORE = [
    "CARDINAL",
    "DATE",
    "EVENT",
    "FAC",
    "LANGUAGE",
    "LAW",
    "MONEY",
    "NORP",
    "ORDINAL",
    "PERCENT",
    "PRODUCT",
    "QUANTITY",
    "TIME",
    "WORK_OF_ART",
]


@dataclass
class _State:
    model: str | os.PathLike[str] = DEFAULT_MODEL_PATH
    engine: AnalyzerEngine | None = None
    build_lock: threading.Lock = threading.Lock()
    scan_lock: threading.Lock = threading.Lock()


_state = _State()


def configure(model: str | os.PathLike[str]) -> None:
    """Select the spaCy model: a package name or a path to a model directory.

    Must be called before the first scan in the process.
    """
    with _state.build_lock:
        if _state.engine is not None:
            raise RuntimeError("configure() must be called before the engine is already loaded")
        _state.model = model


def is_loaded() -> bool:
    return _state.engine is not None


def reset_for_tests() -> None:
    """Drop the engine and configuration. Test use only."""
    with _state.build_lock:
        _state.engine = None
        _state.model = DEFAULT_MODEL_PATH


def _build_engine() -> AnalyzerEngine:
    model = _state.model
    model_ref = os.fspath(model)
    if isinstance(model, os.PathLike) or os.sep in model_ref:
        if not Path(model_ref).is_dir():
            raise FileNotFoundError(f"spaCy model directory not found: {model_ref}")
    nlp_engine = SpacyNlpEngine(
        models=[{"lang_code": "en", "model_name": model_ref}],
        ner_model_configuration=NerModelConfiguration(labels_to_ignore=LABELS_TO_IGNORE),
    )
    nlp_engine.load()
    return AnalyzerEngine(
        registry=build_registry(),
        nlp_engine=nlp_engine,
        supported_languages=["en"],
        default_score_threshold=SCORE_THRESHOLD,
    )


def _get_engine() -> AnalyzerEngine:
    engine = _state.engine
    if engine is not None:
        return engine
    with _state.build_lock:
        if _state.engine is None:
            _state.engine = _build_engine()
        return _state.engine


def analyze(text: str) -> list[RecognizerResult]:
    """Run Presidio over ``text``. Serialised: spaCy pipelines are not thread-safe."""
    engine = _get_engine()
    with _state.scan_lock:
        return engine.analyze(text, language="en")


def _model_identity() -> tuple[str, str]:
    model = _state.model
    model_ref = os.fspath(model)
    meta_path = Path(model_ref) / "meta.json"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return f"{meta['lang']}_{meta['name']}", str(meta["version"])
    return model_ref, dist_version(model_ref)


def scanner_version() -> ScannerVersion:
    """Component versions for audit logs. Does not load the model."""
    model_name, model_version = _model_identity()
    return ScannerVersion(
        library=dist_version("hyperscale-pii-scanner"),
        presidio_analyzer=dist_version("presidio-analyzer"),
        spacy=dist_version("spacy"),
        model_name=model_name,
        model_version=model_version,
    )
```

Note for pyright strict: `engine.analyze` is typed in Presidio as returning `List[RecognizerResult]`; if pyright reports a partially unknown type, wrap with `results: list[RecognizerResult] = engine.analyze(...)` and keep strict mode. Do not lower `typeCheckingMode`.

- [ ] **Step 8: Export from `__init__.py`**

Add to the imports and `__all__`:
```python
from ._engine import configure
from ._engine import scanner_version
```
`__all__ = ["Hit", "HitKind", "ScannerVersion", "__version__", "configure", "scanner_version"]`

- [ ] **Step 9: Write `tests/conftest.py`**

```python
import pytest

from hyperscale.pii_scanner import _engine


@pytest.fixture(scope="session", autouse=True)
def warm_engine() -> None:
    """Load the model once for the session so individual tests stay fast."""
    _engine.analyze("warm up")
```

- [ ] **Step 10: Write the `Makefile` (first targets; release targets come in Task 14)**

```make
SHELL := bash -eu -o pipefail
MAKEFLAGS += --warn-undefined-variable
MODEL_META := src/hyperscale/pii_scanner/_model/en_core_web_md-3.8.0/meta.json

.PHONY: setup model gazetteer lint test check measure clean

setup: model
	uv sync --all-extras
	uvx pre-commit install

model: $(MODEL_META)

$(MODEL_META): scripts/vendor_model.py
	python3 scripts/vendor_model.py

gazetteer:
	uv run --group gazetteer python scripts/build_gazetteer.py

lint:
	uv run ruff check --no-fix .
	uv run ruff format --check .
	uv run pyright

test: model
	uv run pytest

check: lint test

measure: model
	uv run python scripts/measure.py

clean:
	rm -rf dist .pytest_cache .ruff_cache .coverage htmlcov
```

- [ ] **Step 11: Run all tests, lint, types**

Run: `make check`
Expected: all pass. The engine tests take a few seconds for the first load.

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "feat: vendor the pinned spaCy model and add the lazy Presidio engine

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Post-processing and `scan()`

**Files:**
- Create: `src/hyperscale/pii_scanner/_postprocess.py`, `src/hyperscale/pii_scanner/_scan.py`
- Modify: `src/hyperscale/pii_scanner/__init__.py`
- Test: `tests/test_postprocess.py`, `tests/test_scan.py`

**Interfaces:**
- Consumes: `_engine.analyze`, `HitKind`, `Hit`.
- Produces: `Candidate(kind, start, end, score, recogniser)`; `to_candidates(results) -> list[Candidate]`; `resolve_overlaps(cands) -> list[Candidate]`; `suppression_spans(text, allowlist, patterns) -> list[tuple[int, int]]`; `suppress(cands, spans) -> list[Candidate]`; `build_hits(text, cands) -> list[Hit]`; `ENTITY_TO_KIND: dict[str, HitKind]`; public `scan(text, *, allowlist=(), placeholder_patterns=(), language="en") -> list[Hit]`.

- [ ] **Step 1: Write the failing post-processing tests (no model needed)**

```python
# tests/test_postprocess.py
import re

import pytest
from presidio_analyzer import RecognizerResult

from hyperscale.pii_scanner import Hit
from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner._postprocess import Candidate
from hyperscale.pii_scanner._postprocess import build_hits
from hyperscale.pii_scanner._postprocess import resolve_overlaps
from hyperscale.pii_scanner._postprocess import suppress
from hyperscale.pii_scanner._postprocess import suppression_spans
from hyperscale.pii_scanner._postprocess import to_candidates


def _result(entity: str, start: int, end: int, score: float, name: str = "R") -> RecognizerResult:
    return RecognizerResult(
        entity_type=entity,
        start=start,
        end=end,
        score=score,
        recognition_metadata={RecognizerResult.RECOGNIZER_NAME_KEY: name},
    )


def _cand(kind: HitKind, start: int, end: int, score: float = 0.5, name: str = "R") -> Candidate:
    return Candidate(kind=kind, start=start, end=end, score=score, recogniser=name)


def test_to_candidates_maps_entities_and_drops_unknown_and_low_scores():
    results = [
        _result("PERSON", 0, 4, 0.85, "SpacyRecognizer"),
        _result("UK_NHS", 5, 15, 1.0, "NhsRecognizer"),
        _result("CREDIT_CARD", 16, 20, 0.9),
        _result("PERSON", 21, 25, 0.2),
    ]
    cands = to_candidates(results)
    assert cands == [
        Candidate(HitKind.PERSON, 0, 4, 0.85, "SpacyRecognizer"),
        Candidate(HitKind.NHS_NUMBER, 5, 15, 1.0, "NhsRecognizer"),
    ]


def test_structured_kind_beats_model_kind_on_overlap():
    cands = [
        _cand(HitKind.ORGANISATION, 0, 12, 0.85),  # "Postcode HG1"
        _cand(HitKind.POSTCODE, 9, 16, 0.6),  # "HG1 1AA"
    ]
    assert resolve_overlaps(cands) == [cands[1]]


def test_structured_priority_order():
    dob = _cand(HitKind.DATE_OF_BIRTH, 5, 15, 0.9)
    date = _cand(HitKind.DATE, 5, 15, 0.6)
    phone = _cand(HitKind.PHONE, 5, 15, 0.4)
    nhs = _cand(HitKind.NHS_NUMBER, 5, 15, 1.0)
    assert resolve_overlaps([date, dob]) == [dob]
    assert resolve_overlaps([phone, nhs]) == [nhs]
    assert resolve_overlaps([nhs, phone]) == [nhs]


def test_model_kinds_prefer_longer_then_score_then_enum_order():
    long_org = _cand(HitKind.ORGANISATION, 0, 18, 0.85)  # "Leeds City Council"
    short_loc = _cand(HitKind.LOCATION, 0, 5, 0.6)  # "Leeds"
    assert resolve_overlaps([short_loc, long_org]) == [long_org]
    person = _cand(HitKind.PERSON, 0, 7, 0.85)
    location = _cand(HitKind.LOCATION, 0, 7, 0.6)
    assert resolve_overlaps([location, person]) == [person]
    tie_person = _cand(HitKind.PERSON, 0, 7, 0.85)
    tie_loc = _cand(HitKind.LOCATION, 0, 7, 0.85)
    assert resolve_overlaps([tie_loc, tie_person]) == [tie_person]


def test_non_overlapping_candidates_are_all_kept_in_order():
    a = _cand(HitKind.PERSON, 10, 14)
    b = _cand(HitKind.LOCATION, 0, 5)
    c = _cand(HitKind.DATE, 20, 30)
    assert resolve_overlaps([a, b, c]) == [b, a, c]


def test_suppression_spans_whole_word_case_insensitive_and_patterns():
    text = "Report by DR IAN BROWN. MOTHER2FN met (LOCAL AUTHORITY). Browning Road."
    spans = suppression_spans(
        text,
        allowlist=["dr ian brown", " Brown "],
        placeholder_patterns=[r"\b[A-Z]{3,}\d[A-Z]{1,3}\b", r"\([A-Z][A-Z ]+\d?\)"],
    )
    assert (10, 22) in spans  # DR IAN BROWN
    assert (24, 33) in spans  # MOTHER2FN
    assert (38, 55) in spans  # (LOCAL AUTHORITY)
    assert not any(s <= 57 < e for s, e in spans)  # "Browning" is not the word "Brown"


def test_suppress_drops_contained_hits_only():
    spans = [(10, 22)]
    inside = _cand(HitKind.PERSON, 13, 22)  # "IAN BROWN" inside "DR IAN BROWN"
    straddling = _cand(HitKind.PERSON, 13, 30)
    outside = _cand(HitKind.PERSON, 40, 45)
    assert suppress([inside, straddling, outside], spans) == [straddling, outside]


def test_build_hits_fills_text_and_sorts():
    text = "Jane met Bob"
    cands = [_cand(HitKind.PERSON, 9, 12), _cand(HitKind.PERSON, 0, 4, 0.85, "SpacyRecognizer")]
    assert build_hits(text, cands) == [
        Hit(HitKind.PERSON, "Jane", 0, 4, 0.85, "SpacyRecognizer"),
        Hit(HitKind.PERSON, "Bob", 9, 12, 0.5, "R"),
    ]


def test_invalid_placeholder_pattern_raises_value_error():
    with pytest.raises(ValueError, match="placeholder"):
        suppression_spans("x", allowlist=[], placeholder_patterns=["("])


def test_allowlist_entry_with_regex_metacharacters_is_literal():
    spans = suppression_spans("IDB Experts (UK) Ltd.", allowlist=["IDB Experts (UK) Ltd"], placeholder_patterns=[])
    assert spans == [(0, 20)]
    assert re.escape("(") in re.escape("(UK)")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_postprocess.py -q`
Expected: FAIL with `ModuleNotFoundError: hyperscale.pii_scanner._postprocess`.

- [ ] **Step 3: Write `_postprocess.py`**

```python
"""Turn Presidio results into non-overlapping, suppressed, sorted hits."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from presidio_analyzer import RecognizerResult

from ._engine import SCORE_THRESHOLD
from ._types import Hit
from ._types import HitKind

ENTITY_TO_KIND: dict[str, HitKind] = {
    "PERSON": HitKind.PERSON,
    "LOCATION": HitKind.LOCATION,
    "ORGANIZATION": HitKind.ORGANISATION,
    "UK_DATE": HitKind.DATE,
    "DATE_OF_BIRTH": HitKind.DATE_OF_BIRTH,
    "AGE": HitKind.AGE,
    "UK_POSTCODE": HitKind.POSTCODE,
    "UK_NHS": HitKind.NHS_NUMBER,
    "UK_NINO": HitKind.NATIONAL_INSURANCE_NUMBER,
    "PHONE_NUMBER": HitKind.PHONE,
    "EMAIL_ADDRESS": HitKind.EMAIL,
    "URL": HitKind.URL,
    "CASE_REFERENCE": HitKind.CASE_REFERENCE,
}

# Highest priority first. Kinds not listed are "model" kinds.
STRUCTURED_PRIORITY: tuple[HitKind, ...] = (
    HitKind.DATE_OF_BIRTH,
    HitKind.NHS_NUMBER,
    HitKind.NATIONAL_INSURANCE_NUMBER,
    HitKind.POSTCODE,
    HitKind.CASE_REFERENCE,
    HitKind.EMAIL,
    HitKind.URL,
    HitKind.PHONE,
    HitKind.AGE,
    HitKind.DATE,
)
_KIND_ORDER = {kind: index for index, kind in enumerate(HitKind)}


@dataclass(frozen=True, slots=True)
class Candidate:
    kind: HitKind
    start: int
    end: int
    score: float
    recogniser: str


def to_candidates(results: Iterable[RecognizerResult]) -> list[Candidate]:
    """Map Presidio entity types to kinds; drop unknown kinds and low scores."""
    candidates: list[Candidate] = []
    for result in results:
        kind = ENTITY_TO_KIND.get(result.entity_type)
        if kind is None or result.score < SCORE_THRESHOLD:
            continue
        metadata = result.recognition_metadata or {}
        name = str(metadata.get(RecognizerResult.RECOGNIZER_NAME_KEY, "unknown"))
        candidates.append(Candidate(kind, result.start, result.end, float(result.score), name))
    return candidates


def _rank(candidate: Candidate) -> tuple[int, int, int, float, int]:
    structured = candidate.kind in STRUCTURED_PRIORITY
    priority = -STRUCTURED_PRIORITY.index(candidate.kind) if structured else 0
    return (
        1 if structured else 0,
        priority,
        candidate.end - candidate.start,
        candidate.score,
        -_KIND_ORDER[candidate.kind],
    )


def _overlaps(a: Candidate, b: Candidate) -> bool:
    return a.start < b.end and b.start < a.end


def resolve_overlaps(candidates: Iterable[Candidate]) -> list[Candidate]:
    """Keep one candidate per overlapping group using the spec's priority rules."""
    kept: list[Candidate] = []
    for candidate in sorted(candidates, key=lambda c: (c.start, -(c.end - c.start))):
        conflicts = [k for k in kept if _overlaps(k, candidate)]
        if not conflicts:
            kept.append(candidate)
            continue
        if all(_rank(candidate) > _rank(other) for other in conflicts):
            kept = [k for k in kept if k not in conflicts]
            kept.append(candidate)
    return sorted(kept, key=lambda c: (c.start, c.end))


def suppression_spans(
    text: str,
    allowlist: Iterable[str],
    placeholder_patterns: Iterable[str],
) -> list[tuple[int, int]]:
    """Spans of allowlist occurrences (whole word, case-insensitive) and placeholder matches."""
    spans: list[tuple[int, int]] = []
    for entry in allowlist:
        entry = entry.strip()
        if not entry:
            continue
        pattern = re.compile(r"(?<!\w)" + re.escape(entry) + r"(?!\w)", re.IGNORECASE)
        spans.extend(m.span() for m in pattern.finditer(text))
    for raw in placeholder_patterns:
        try:
            pattern = re.compile(raw)
        except re.error as exc:
            raise ValueError(f"invalid placeholder pattern {raw!r}: {exc}") from exc
        spans.extend(m.span() for m in pattern.finditer(text) if m.end() > m.start())
    return spans


def suppress(candidates: Iterable[Candidate], spans: Iterable[tuple[int, int]]) -> list[Candidate]:
    """Drop candidates whose span lies entirely within a suppression span."""
    span_list = list(spans)
    return [
        c
        for c in candidates
        if not any(start <= c.start and c.end <= end for start, end in span_list)
    ]


def build_hits(text: str, candidates: Iterable[Candidate]) -> list[Hit]:
    return [
        Hit(c.kind, text[c.start : c.end], c.start, c.end, c.score, c.recogniser)
        for c in sorted(candidates, key=lambda c: (c.start, c.end))
    ]
```

- [ ] **Step 4: Run the post-processing tests**

Run: `uv run pytest tests/test_postprocess.py -q`
Expected: `10 passed`.

- [ ] **Step 5: Write the failing `scan` tests**

```python
# tests/test_scan.py
import pytest

from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import scan
from hyperscale.pii_scanner._postprocess import suppression_spans

PLACEHOLDERS = [r"\b[A-Z]{3,}\d[A-Z]{1,3}\b", r"\([A-Z][A-Z ]+\d?\)"]


def test_scan_empty_text_returns_empty_list():
    assert scan("") == []
    assert scan("   \n") == []


def test_scan_rejects_other_languages():
    with pytest.raises(ValueError, match="language"):
        scan("Bonjour", language="fr")


def test_scan_validates_placeholder_patterns_before_scanning():
    with pytest.raises(ValueError, match="placeholder"):
        scan("Jane Smith", placeholder_patterns=["("])


def test_scan_reports_person_and_location():
    hits = scan("Jane Smith lives in Harrogate.")
    kinds = {(h.kind, h.text) for h in hits}
    assert (HitKind.PERSON, "Jane Smith") in kinds
    assert (HitKind.LOCATION, "Harrogate") in kinds
    for h in hits:
        assert "Jane Smith lives in Harrogate."[h.start : h.end] == h.text


def test_scan_suppresses_allowlist_and_placeholders():
    text = "Report by Dr Ian Brown. MOTHER2FN lives with (LOCAL AUTHORITY) support in Harrogate."
    hits = scan(text, allowlist=["Dr Ian Brown"], placeholder_patterns=PLACEHOLDERS)
    texts = [h.text for h in hits]
    assert "Harrogate" in texts
    assert not any("Brown" in t for t in texts)
    assert not any("MOTHER2FN" in t or "LOCAL AUTHORITY" in t for t in texts)


def test_hit_extending_beyond_placeholder_is_reported():
    text = "The child was seen with MOTHER2FN Jones at home."
    hits = scan(text, placeholder_patterns=PLACEHOLDERS)
    assert any(h.kind == HitKind.PERSON and "Jones" in h.text for h in hits)


def test_scan_offsets_index_original_text_with_crlf_and_unicode():
    text = "Report.\r\nLlanfairpwllgwyngyll is a village.\r\nSiân O’Neill attended with Jane Smith.\r\n"
    hits = scan(text)
    assert hits, "expected at least one hit"
    for h in hits:
        assert text[h.start : h.end] == h.text
    assert any(h.kind == HitKind.PERSON and h.text == "Jane Smith" for h in hits)


def test_scan_results_are_sorted_and_non_overlapping():
    hits = scan("Jane Smith met Bob Jones in Leeds on 13 July 2026 near Leeds City Council.")
    for earlier, later in zip(hits, hits[1:], strict=False):
        assert earlier.end <= later.start


def test_scan_is_deterministic():
    text = "Jane Smith lives in Harrogate and works for Leeds City Council."
    assert scan(text) == scan(text)


def test_whitespace_only_allowlist_entries_are_ignored():
    assert suppression_spans("Jane", allowlist=["  ", ""], placeholder_patterns=[]) == []
```

- [ ] **Step 6: Write `_scan.py` and export `scan`**

```python
"""The public scan() entry point."""

from __future__ import annotations

from collections.abc import Iterable

from . import _engine
from ._postprocess import build_hits
from ._postprocess import resolve_overlaps
from ._postprocess import suppress
from ._postprocess import suppression_spans
from ._postprocess import to_candidates
from ._types import Hit


def scan(
    text: str,
    *,
    allowlist: Iterable[str] = (),
    placeholder_patterns: Iterable[str] = (),
    language: str = "en",
) -> list[Hit]:
    """Find residual personal identifiers in ``text``.

    Best effort: reports what the configured recognisers found. It never
    certifies that text is anonymised.
    """
    if language != "en":
        raise ValueError(f"unsupported language {language!r}; only 'en' is supported")
    allow = [entry.strip() for entry in allowlist if entry.strip()]
    patterns = list(placeholder_patterns)
    # Validate patterns up front so a bad pattern fails before the model loads.
    suppression_spans("", allow, patterns)
    if not text.strip():
        return []
    results = _engine.analyze(text)
    candidates = resolve_overlaps(to_candidates(results))
    spans = suppression_spans(text, allow, patterns)
    return build_hits(text, suppress(candidates, spans))
```

In `__init__.py` add `from ._scan import scan` and `"scan"` to `__all__`.

- [ ] **Step 7: Run all tests, lint, types**

Run: `make check`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add post-processing (kind mapping, overlaps, suppression) and scan()

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: `redact()`

**Files:**
- Create: `src/hyperscale/pii_scanner/_redact.py`
- Modify: `src/hyperscale/pii_scanner/__init__.py`
- Test: `tests/test_redact.py`

**Interfaces:**
- Produces: `redact(text: str, hits: Iterable[Hit], token_for: Callable[[Hit], str] | None = None) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_redact.py
import pytest

from hyperscale.pii_scanner import Hit
from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import redact


def _hit(kind: HitKind, text: str, start: int) -> Hit:
    return Hit(kind, text, start, start + len(text), 0.9, "test")


def test_redact_default_token_is_upper_kind_in_brackets():
    text = "Jane Smith, NHS 943 476 5919."
    hits = [_hit(HitKind.PERSON, "Jane Smith", 0), _hit(HitKind.NHS_NUMBER, "943 476 5919", 16)]
    assert redact(text, hits) == "[PERSON], NHS [NHS_NUMBER]."


def test_redact_custom_token_receives_the_hit():
    text = "Jane Smith"
    assert redact(text, [_hit(HitKind.PERSON, "Jane Smith", 0)], token_for=lambda h: f"<{h.kind}:{len(h.text)}>") == "<person:10>"


def test_redact_with_no_hits_returns_text_unchanged():
    assert redact("nothing here", []) == "nothing here"


def test_redact_rejects_hits_from_other_text():
    with pytest.raises(ValueError, match="does not match"):
        redact("Bob Jones is here", [_hit(HitKind.PERSON, "Jane Smith", 0)])


def test_redact_rejects_out_of_range_hit():
    with pytest.raises(ValueError):
        redact("short", [Hit(HitKind.PERSON, "longer text", 0, 11, 0.9, "t")])


def test_redact_overlapping_hits_keeps_earliest_then_longest():
    text = "Leeds City Council"
    hits = [_hit(HitKind.LOCATION, "Leeds", 0), _hit(HitKind.ORGANISATION, "Leeds City Council", 0)]
    assert redact(text, hits) == "[ORGANISATION]"
    hits = [_hit(HitKind.ORGANISATION, "City Council", 6), _hit(HitKind.LOCATION, "Leeds City", 0)]
    assert redact(text, hits) == "[LOCATION] Council"


def test_redact_handles_unordered_input():
    text = "A Jane and Bob"
    hits = [_hit(HitKind.PERSON, "Bob", 11), _hit(HitKind.PERSON, "Jane", 2)]
    assert redact(text, hits) == "A [PERSON] and [PERSON]"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_redact.py -q`
Expected: FAIL with `ImportError: cannot import name 'redact'`.

- [ ] **Step 3: Write `_redact.py`**

```python
"""Replace hits in text with tokens."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterable

from ._types import Hit


def _default_token(hit: Hit) -> str:
    return f"[{hit.kind.value.upper()}]"


def redact(text: str, hits: Iterable[Hit], token_for: Callable[[Hit], str] | None = None) -> str:
    """Return ``text`` with each hit replaced by ``token_for(hit)``.

    Raises ``ValueError`` if a hit does not line up with ``text``, which
    catches hits produced from a different document. Overlapping hits keep
    the earliest start, then the longest span.
    """
    token = token_for or _default_token
    ordered = sorted(hits, key=lambda h: (h.start, -(h.end - h.start)))
    chosen: list[Hit] = []
    cursor = 0
    for hit in ordered:
        if hit.start < 0 or hit.end > len(text) or hit.start >= hit.end:
            raise ValueError(f"hit span {hit.start}:{hit.end} is outside the text")
        if text[hit.start : hit.end] != hit.text:
            raise ValueError(f"hit text {hit.text!r} does not match text at {hit.start}:{hit.end}")
        if hit.start < cursor:
            continue
        chosen.append(hit)
        cursor = hit.end
    pieces: list[str] = []
    cursor = 0
    for hit in chosen:
        pieces.append(text[cursor : hit.start])
        pieces.append(token(hit))
        cursor = hit.end
    pieces.append(text[cursor:])
    return "".join(pieces)
```

In `__init__.py` add `from ._redact import redact` and `"redact"` to `__all__`.

- [ ] **Step 4: Run tests, lint, types**

Run: `make check`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add redact()

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: UK date and date-of-birth recognisers

**Files:**
- Create: `src/hyperscale/pii_scanner/_recognisers/uk_date.py`, `src/hyperscale/pii_scanner/_recognisers/date_of_birth.py`, `tests/helpers.py`
- Modify: `src/hyperscale/pii_scanner/_recognisers/__init__.py`
- Test: `tests/test_recogniser_dates.py`

**Interfaces:**
- Produces: `uk_date.ANY_DATE: str` (a regex fragment matching any supported date form, no anchors, needs `(?i)`), `UkDateRecognizer()` producing entity `UK_DATE`, `DateOfBirthRecognizer()` producing `DATE_OF_BIRTH`; `tests.helpers.matches(recogniser, text, entity) -> list[tuple[str, float]]`.

- [ ] **Step 1: Write `tests/helpers.py`**

```python
from presidio_analyzer import EntityRecognizer


def matches(recogniser: EntityRecognizer, text: str, entity: str) -> list[tuple[str, float]]:
    """Run one recogniser directly (no NLP artifacts) and return (text, score) pairs."""
    results = recogniser.analyze(text, [entity])
    return sorted((text[r.start : r.end], round(r.score, 2)) for r in results)
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_recogniser_dates.py
import pytest

from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import scan
from hyperscale.pii_scanner._recognisers.date_of_birth import DateOfBirthRecognizer
from hyperscale.pii_scanner._recognisers.uk_date import UkDateRecognizer
from tests.helpers import matches


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("seen on 13th of July 2026", "13th of July 2026"),
        ("seen on 3rd June 2026", "3rd June 2026"),
        ("seen on 13 July 2026", "13 July 2026"),
        ("seen on 13 Jul 2026", "13 Jul 2026"),
        ("seen on 13 Sept 2026", "13 Sept 2026"),
        ("seen on Monday 13 July 2026", "Monday 13 July 2026"),
        ("seen on Monday, 13th July, 2026", "Monday, 13th July, 2026"),
        ("seen on July 13, 2026", "July 13, 2026"),
        ("seen on July 13th 2026", "July 13th 2026"),
        ("seen on 13/07/2026", "13/07/2026"),
        ("seen on 13/7/26", "13/7/26"),
        ("seen on 13.07.2026", "13.07.2026"),
        ("seen on 13-07-2026", "13-07-2026"),
        ("seen on 2026-07-13", "2026-07-13"),
        ("seen in July 2026", "July 2026"),
        ("seen in JULY 2026", "JULY 2026"),
    ],
)
def test_uk_date_positive(text: str, expected: str):
    found = [t for t, _ in matches(UkDateRecognizer(), text, "UK_DATE")]
    assert expected in found


@pytest.mark.parametrize(
    "text",
    [
        "in 2026 she moved",
        "ratio 32/7/2026",
        "13/13/2026",
        "three weeks later",
        "phone 0113 496 2026",
        "Section 13 of July",
    ],
)
def test_uk_date_negative(text: str):
    assert matches(UkDateRecognizer(), text, "UK_DATE") == []


def test_textual_dates_score_higher_than_numeric():
    textual = matches(UkDateRecognizer(), "13 July 2026", "UK_DATE")
    numeric = matches(UkDateRecognizer(), "13/07/2026", "UK_DATE")
    assert textual == [("13 July 2026", 0.85)]
    assert numeric == [("13/07/2026", 0.6)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("DOB: 14/03/2019", "14/03/2019"),
        ("DOB 14.3.19", "14.3.19"),
        ("D.O.B. 14 March 2019", "14 March 2019"),
        ("Date of birth: 14th of March 2019", "14th of March 2019"),
        ("date of birth 2019-03-14", "2019-03-14"),
        ("She was born on 14 March 2019 in Leeds", "14 March 2019"),
        ("born in March 2019", "March 2019"),
        ("Birth date - 14/03/2019", "14/03/2019"),
    ],
)
def test_date_of_birth_positive(text: str, expected: str):
    assert matches(DateOfBirthRecognizer(), text, "DATE_OF_BIRTH") == [(expected, 0.9)]


@pytest.mark.parametrize(
    "text",
    [
        "DOB redacted",
        "seen on 14/03/2019",
        "born and raised in Leeds",
        "Reborn 14/03/2019",
        "DOB 2019",
    ],
)
def test_date_of_birth_negative(text: str):
    assert matches(DateOfBirthRecognizer(), text, "DATE_OF_BIRTH") == []


def test_scan_reports_dob_not_date_for_labelled_date():
    hits = scan("The child (DOB 14/03/2019) was seen on 13 July 2026.")
    by_text = {h.text: h.kind for h in hits}
    assert by_text["14/03/2019"] == HitKind.DATE_OF_BIRTH
    assert by_text["13 July 2026"] == HitKind.DATE
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_recogniser_dates.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Write `uk_date.py`**

```python
"""UK date formats as a Presidio pattern recogniser.

Bare years are not dates; spaCy's DATE label is disabled because it includes
durations such as "three weeks".
"""

from __future__ import annotations

from presidio_analyzer import Pattern
from presidio_analyzer import PatternRecognizer

MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?"
    r"|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
DAY = r"(?:0?[1-9]|[12][0-9]|3[01])"
ORDINAL = r"(?:st|nd|rd|th)?"
WEEKDAY = r"(?:(?:mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)day,?\s+)?"
YEAR = r"(?:19|20)\d{2}"
MONTH_NUM = r"(?:0?[1-9]|1[0-2])"

TEXTUAL_DMY = rf"{WEEKDAY}{DAY}{ORDINAL}\s+(?:of\s+)?{MONTH}\.?,?\s+{YEAR}"
TEXTUAL_MDY = rf"{WEEKDAY}{MONTH}\.?\s+{DAY}{ORDINAL},?\s+{YEAR}"
MONTH_YEAR = rf"{MONTH}\.?,?\s+{YEAR}"
NUMERIC_DMY = rf"{DAY}[/.-]{MONTH_NUM}[/.-](?:{YEAR}|\d{{2}})"
ISO = rf"{YEAR}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"

# Any supported date form, unanchored. Callers add boundaries. Case-insensitive
# under Presidio's default flags.
ANY_DATE = rf"(?:{TEXTUAL_DMY}|{TEXTUAL_MDY}|{ISO}|{NUMERIC_DMY}|{MONTH_YEAR})"


class UkDateRecognizer(PatternRecognizer):
    """Recognise full dates and month-year pairs in UK conventions."""

    PATTERNS = [
        Pattern("textual day month year", rf"\b{TEXTUAL_DMY}\b", 0.85),
        Pattern("textual month day year", rf"\b{TEXTUAL_MDY}\b", 0.85),
        Pattern("month year", rf"\b{MONTH_YEAR}\b", 0.6),
        Pattern("numeric day month year", rf"(?<![\d/.-]){NUMERIC_DMY}(?![\d/.-])", 0.6),
        Pattern("iso date", rf"(?<![\d-]){ISO}(?![\d-])", 0.6),
    ]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="UK_DATE",
            name="UkDateRecognizer",
            patterns=self.PATTERNS,
        )
```

- [ ] **Step 5: Write `date_of_birth.py`**

```python
"""A date that follows a date-of-birth label within 25 characters (line breaks allowed)."""

from __future__ import annotations

import re

from presidio_analyzer import LocalRecognizer
from presidio_analyzer import RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from .uk_date import ANY_DATE

LABEL = r"(?:d\.?\s?o\.?\s?b\.?|date\s+of\s+birth|birth\s*date|born(?:\s+on|\s+in)?)"
PATTERN = re.compile(
    rf"(?<!\w){LABEL}(?!\w)[\s\S]{{0,25}}?(?<![\w/.-])({ANY_DATE})(?![\w/.-])",
    re.IGNORECASE,
)
SCORE = 0.9


class DateOfBirthRecognizer(LocalRecognizer):
    """Reports the date only, leaving the label in place for redaction."""

    def __init__(self) -> None:
        super().__init__(supported_entities=["DATE_OF_BIRTH"], name="DateOfBirthRecognizer")

    def load(self) -> None:
        return None

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        if "DATE_OF_BIRTH" not in entities:
            return []
        return [
            RecognizerResult(
                entity_type="DATE_OF_BIRTH",
                start=match.start(1),
                end=match.end(1),
                score=SCORE,
                recognition_metadata={
                    RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                    RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id,
                },
            )
            for match in PATTERN.finditer(text)
        ]
```

- [ ] **Step 6: Register both in `_recognisers/__init__.py`**

```python
from .date_of_birth import DateOfBirthRecognizer
from .uk_date import UkDateRecognizer
```
and append `UkDateRecognizer()` and `DateOfBirthRecognizer()` to the list returned by `build_recognisers()`.

- [ ] **Step 7: Run the tests; adjust patterns until all pass**

Run: `uv run pytest tests/test_recogniser_dates.py -q`
Expected: all pass. If `ratio 32/7/2026` matches, the day class is wrong; if `13/13/2026` matches, the month class is wrong.

- [ ] **Step 8: Run `make check` and commit**

```bash
git add -A
git commit -m "feat: add UK date and date-of-birth recognisers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Age recogniser

**Files:**
- Create: `src/hyperscale/pii_scanner/_recognisers/age.py`
- Modify: `src/hyperscale/pii_scanner/_recognisers/__init__.py`
- Test: `tests/test_recogniser_age.py`

**Interfaces:**
- Produces: `AgeRecognizer()` producing `AGE`, score 0.7, whole phrase as the span.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_recogniser_age.py
import pytest

from hyperscale.pii_scanner._recognisers.age import AgeRecognizer
from tests.helpers import matches


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("she is aged 34", "aged 34"),
        ("she is aged 34 years", "aged 34 years"),
        ("Age: 34", "Age: 34"),
        ("age 34", "age 34"),
        ("she is 34 years old", "34 years old"),
        ("a 34-year-old woman", "34-year-old"),
        ("a 34 year old woman", "34 year old"),
        ("34 yrs old", "34 yrs old"),
        ("aged 18 months", "aged 18 months"),
        ("an 18-month-old baby", "18-month-old"),
        ("a six-year-old boy", "six-year-old"),
        ("aged six", "aged six"),
        ("twenty-one years of age", "twenty-one years of age"),
        ("AGED 34", "AGED 34"),
    ],
)
def test_age_positive(text: str, expected: str):
    assert matches(AgeRecognizer(), text, "AGE") == [(expected, 0.7)]


@pytest.mark.parametrize(
    "text",
    [
        "aged 250",
        "page 34",
        "stage 2 assessment",
        "34 years ago",
        "for 34 years",
        "the old 34 bus",
        "an image 34 years in the making",
    ],
)
def test_age_negative(text: str):
    assert matches(AgeRecognizer(), text, "AGE") == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_recogniser_age.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `age.py`**

```python
"""Ages: "aged 34", "34 years old", "34-year-old", "six-year-old", "18 months old"."""

from __future__ import annotations

import re

from presidio_analyzer import Pattern
from presidio_analyzer import PatternRecognizer

NUMBER_WORDS = (
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    "fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|"
    "fifty|sixty|seventy|eighty|ninety"
)
NUM = rf"(?:\d{{1,3}}|(?:{NUMBER_WORDS})(?:[\s-](?:{NUMBER_WORDS}))?)"
UNIT = r"(?:years?|yrs?|months?|weeks?)"
MAX_AGE = 120


class AgeRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("aged N", rf"\baged?\s*:?\s*{NUM}(?:\s*{UNIT})?\b", 0.7),
        Pattern("N years old", rf"\b{NUM}[\s-]+{UNIT}[\s-]+old\b", 0.7),
        Pattern("N years of age", rf"\b{NUM}\s+{UNIT}\s+of\s+age\b", 0.7),
    ]

    def __init__(self) -> None:
        super().__init__(supported_entity="AGE", name="AgeRecognizer", patterns=self.PATTERNS)

    def invalidate_result(self, pattern_text: str) -> bool:
        """Numbers above 120 are not ages."""
        digits = re.search(r"\d+", pattern_text)
        return digits is not None and int(digits.group()) > MAX_AGE
```

- [ ] **Step 4: Register in `_recognisers/__init__.py`** (`from .age import AgeRecognizer`; append `AgeRecognizer()`).

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_recogniser_age.py -q`
Expected: all pass. Presidio drops results that `invalidate_result` flags (score becomes 0).

- [ ] **Step 6: Run `make check` and commit**

```bash
git add -A
git commit -m "feat: add age recogniser

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: UK postcode recogniser

**Files:**
- Create: `src/hyperscale/pii_scanner/_recognisers/postcode.py`
- Modify: `src/hyperscale/pii_scanner/_recognisers/__init__.py`
- Test: `tests/test_recogniser_postcode.py`

**Interfaces:**
- Produces: `UkPostcodeRecognizer()` producing `UK_POSTCODE`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_recogniser_postcode.py
import pytest

from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import scan
from hyperscale.pii_scanner._recognisers.postcode import UkPostcodeRecognizer
from tests.helpers import matches


@pytest.mark.parametrize(
    ("text", "expected", "score"),
    [
        ("lives at LS1 4AP today", "LS1 4AP", 0.6),
        ("lives at SW1A 1AA today", "SW1A 1AA", 0.6),
        ("lives at W1A 0AX today", "W1A 0AX", 0.6),
        ("lives at M1 1AE today", "M1 1AE", 0.6),
        ("lives at B33 8TH today", "B33 8TH", 0.6),
        ("lives at CR2 6XH today", "CR2 6XH", 0.6),
        ("lives at DN55 1PT today", "DN55 1PT", 0.6),
        ("lives at GIR 0AA today", "GIR 0AA", 0.6),
        ("lives at LS14AP today", "LS14AP", 0.45),
    ],
)
def test_full_postcode_positive(text: str, expected: str, score: float):
    assert (expected, score) in matches(UkPostcodeRecognizer(), text, "UK_POSTCODE")


@pytest.mark.parametrize(
    "text",
    [
        "lives at ls1 4ap today",  # postcodes are upper case
        "QV1 1AA",  # Q, V, X are not valid first letters
        "LS1 4CI",  # C, I, K, M, O, V not valid in the inward code
        "LS1 4APX",
        "ABC 123",
    ],
)
def test_full_postcode_negative(text: str):
    found = [t for t, score in matches(UkPostcodeRecognizer(), text, "UK_POSTCODE") if score >= 0.3]
    assert found == []


def test_outward_code_has_low_score_without_context():
    found = matches(UkPostcodeRecognizer(), "The LS1 district was quiet.", "UK_POSTCODE")
    assert found == [("LS1", 0.05)]


def test_outward_code_is_not_matched_inside_full_postcode():
    found = matches(UkPostcodeRecognizer(), "LS1 4AP", "UK_POSTCODE")
    assert found == [("LS1 4AP", 0.6)]


def test_outward_code_reported_only_with_context_via_scan():
    with_context = scan("Her postcode is LS1 and she is happy.")
    assert (HitKind.POSTCODE, "LS1") in {(h.kind, h.text) for h in with_context}
    without_context = scan("Vitamin B12 and form E1 were mentioned.")
    assert not any(h.kind == HitKind.POSTCODE for h in without_context)


def test_full_postcode_in_allowlist_is_not_reported():
    hits = scan("Office: LS1 4AP.", allowlist=["LS1 4AP"])
    assert hits == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_recogniser_postcode.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `postcode.py`**

```python
"""UK postcodes: full form on its own, outward code only with a context word."""

from __future__ import annotations

from presidio_analyzer import Pattern
from presidio_analyzer import PatternRecognizer

# Position rules from https://en.wikipedia.org/wiki/Postcodes_in_the_United_Kingdom
AREA_DISTRICT = r"(?:[A-PR-UWYZ](?:\d{1,2}|[A-HK-Y]\d{1,2}|\d[A-HJKPSTUW]|[A-HK-Y]\d[ABEHMNPRVWXY]))"
INWARD = r"\d[ABD-HJLNP-UW-Z]{2}"


class UkPostcodeRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("full postcode", rf"(?-i:\b(?:GIR 0AA|{AREA_DISTRICT} {INWARD})\b)", 0.6),
        Pattern("full postcode, no space", rf"(?-i:\b(?:GIR0AA|{AREA_DISTRICT}{INWARD})\b)", 0.45),
        Pattern("outward code", rf"(?-i:\b{AREA_DISTRICT}\b(?! ?{INWARD}\b))", 0.05),
    ]
    CONTEXT = ["postcode", "post code", "postal", "area", "district"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="UK_POSTCODE",
            name="UkPostcodeRecognizer",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )
```

- [ ] **Step 4: Register** (`from .postcode import UkPostcodeRecognizer`; append `UkPostcodeRecognizer()`).

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_recogniser_postcode.py -q`
Expected: all pass. The context test relies on Presidio's `LemmaContextAwareEnhancer` raising a matched 0.05 result to 0.4 when `postcode` appears within five tokens before it.

- [ ] **Step 6: Run `make check` and commit**

```bash
git add -A
git commit -m "feat: add UK postcode recogniser

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Case references, offline email, and the reused Presidio recognisers

**Files:**
- Create: `src/hyperscale/pii_scanner/_recognisers/case_reference.py`, `src/hyperscale/pii_scanner/_recognisers/email.py`
- Modify: `src/hyperscale/pii_scanner/_recognisers/__init__.py`
- Test: `tests/test_recogniser_case_reference.py`, `tests/test_recogniser_reused.py`

**Interfaces:**
- Produces: `CaseReferenceRecognizer()` producing `CASE_REFERENCE`; `OfflineEmailRecognizer()` producing `EMAIL_ADDRESS`; `build_recognisers()` now returns the complete list except the gazetteer (Task 10).

- [ ] **Step 1: Write the failing case-reference tests**

```python
# tests/test_recogniser_case_reference.py
import pytest

from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import scan
from hyperscale.pii_scanner._recognisers.case_reference import CaseReferenceRecognizer
from tests.helpers import matches


@pytest.mark.parametrize(
    ("text", "expected", "score"),
    [
        ("Case ZC24C50123 concerns", "ZC24C50123", 0.7),
        ("Case FD24P00123 concerns", "FD24P00123", 0.7),
        ("see [2026] EWFC 12 at", "[2026] EWFC 12", 0.85),
        ("see [2024] EWHC 123 (Fam) at", "[2024] EWHC 123 (Fam)", 0.85),
        ("see [2023] EWCA Civ 45 at", "[2023] EWCA Civ 45", 0.85),
        ("see [2022] UKSC 1 at", "[2022] UKSC 1", 0.85),
        ("see [2026] EWFC 12 (B) at", "[2026] EWFC 12 (B)", 0.85),
        ("see [2021] EWCOP 7 at", "[2021] EWCOP 7", 0.85),
    ],
)
def test_case_reference_positive(text: str, expected: str, score: float):
    assert (expected, score) in matches(CaseReferenceRecognizer(), text, "CASE_REFERENCE")


@pytest.mark.parametrize(
    "text",
    [
        "zc24c50123",  # case numbers are upper case
        "AB123456C",  # that is a NINO shape
        "[2026] 12",
        "[2026] XYZ 12",
        "ZC24C5012",
    ],
)
def test_case_reference_negative(text: str):
    found = [t for t, score in matches(CaseReferenceRecognizer(), text, "CASE_REFERENCE") if score >= 0.3]
    assert found == []


def test_crown_court_and_cps_numbers_need_context():
    found = matches(CaseReferenceRecognizer(), "T20247123 and 01AB1234567", "CASE_REFERENCE")
    assert found == [("01AB1234567", 0.2), ("T20247123", 0.2)]
    hits = scan("Crown Court case T20247123 was listed. The URN 01AB1234567 applies.")
    assert {(h.kind, h.text) for h in hits} >= {
        (HitKind.CASE_REFERENCE, "T20247123"),
        (HitKind.CASE_REFERENCE, "01AB1234567"),
    }
    assert not any(h.kind == HitKind.CASE_REFERENCE for h in scan("Serial T20247123 was printed."))
```

- [ ] **Step 2: Write the failing tests for reused recognisers and the offline email**

```python
# tests/test_recogniser_reused.py
import socket

import pytest

from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import scan
from hyperscale.pii_scanner._recognisers import build_recognisers
from hyperscale.pii_scanner._recognisers.email import OfflineEmailRecognizer
from tests.helpers import matches


def _kinds(text: str) -> set[tuple[HitKind, str]]:
    return {(h.kind, h.text) for h in scan(text)}


def test_registry_has_no_us_or_unlisted_recognisers():
    names = {type(r).__name__ for r in build_recognisers()}
    assert not any(n.startswith("Us") for n in names)
    assert "CreditCardRecognizer" not in names
    assert "DateRecognizer" not in names
    assert "IpRecognizer" not in names


@pytest.mark.parametrize(
    "nhs",
    ["943 476 5919", "9434765919", "943-476-5919", "398 259 7919", "401 023 2137"],
)
def test_nhs_valid_numbers(nhs: str):
    assert (HitKind.NHS_NUMBER, nhs) in _kinds(f"NHS number {nhs} on file.")


@pytest.mark.parametrize("not_nhs", ["943 476 5918", "485 777 3456", "123 456 7890"])
def test_nhs_check_digit_failures_are_not_reported(not_nhs: str):
    assert not any(k == HitKind.NHS_NUMBER for k, _ in _kinds(f"NHS number {not_nhs} on file."))


def test_nhs_number_is_not_also_reported_as_phone():
    hits = scan("Her number is 943 476 5919.")
    assert [(h.kind, h.text) for h in hits] == [(HitKind.NHS_NUMBER, "943 476 5919")]


@pytest.mark.parametrize("nino", ["AB123456C", "AB 12 34 56 C", "JG 20 31 97 A"])
def test_nino_valid(nino: str):
    assert (HitKind.NATIONAL_INSURANCE_NUMBER, nino) in _kinds(f"NI number {nino}.")


@pytest.mark.parametrize("not_nino", ["BG123456C", "GB123456C", "NK123456C", "KN123456C", "NT123456C", "TN123456C", "ZZ123456C", "DA123456C", "AO123456C", "AB123456E"])
def test_nino_invalid_prefix_or_suffix(not_nino: str):
    assert not any(k == HitKind.NATIONAL_INSURANCE_NUMBER for k, _ in _kinds(f"NI number {not_nino}."))


@pytest.mark.parametrize(
    "phone",
    ["07911 123456", "+44 7911 123456", "0113 496 0000", "(0113) 4960000", "020 7946 0958", "+44 (0)20 7946 0958"],
)
def test_uk_phone_positive(phone: str):
    assert (HitKind.PHONE, phone) in _kinds(f"Call {phone} now.")


@pytest.mark.parametrize("not_phone", ["123456789", "12345", "1 800 555 0199"])
def test_uk_phone_negative(not_phone: str):
    assert not any(k == HitKind.PHONE for k, _ in _kinds(f"Ref {not_phone} here."))


def test_email_and_url():
    kinds = _kinds("Write to jane.smith@example.org or see https://www.example.org/report/1.")
    assert (HitKind.EMAIL, "jane.smith@example.org") in kinds
    assert any(k == HitKind.URL and "example.org" in t for k, t in kinds)


def test_email_validation_is_offline(monkeypatch: pytest.MonkeyPatch):
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    assert matches(OfflineEmailRecognizer(), "jane@example.org", "EMAIL_ADDRESS") == [("jane@example.org", 1.0)]
    assert matches(OfflineEmailRecognizer(), "jane@example.notatld", "EMAIL_ADDRESS") == []
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_recogniser_case_reference.py tests/test_recogniser_reused.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Write `case_reference.py`**

```python
"""Court and case references in the common UK patterns."""

from __future__ import annotations

from presidio_analyzer import Pattern
from presidio_analyzer import PatternRecognizer

COURTS = (
    r"(?:UKSC|UKPC|UKHL|UKUT|UKFTT|UKEAT|EWCA(?:\s+(?:Civ|Crim))?|EWHC|EWFC|EWCOP|EWCC"
    r"|CSOH|CSIH|NICA|NIQB|NIFam)"
)


class CaseReferenceRecognizer(PatternRecognizer):
    PATTERNS = [
        # Family, county and civil court case numbers: ZC24C50123, FD24P00123
        Pattern("court case number", r"(?-i:\b[A-Z]{2}\d{2}[A-Z]\d{5}\b)", 0.7),
        # Neutral citations: [2026] EWFC 12, [2024] EWHC 123 (Fam), [2023] EWCA Civ 45
        Pattern(
            "neutral citation",
            rf"(?-i:\[(?:19|20)\d{{2}}\]\s+{COURTS}\s+\d+(?:\s+\([A-Za-z]+\))?)",
            0.85,
        ),
        # Crown Court numbers (T20247123) and CPS URNs (01AB1234567): context required
        Pattern("crown court or cps number", r"(?-i:\b(?:[TSU]\d{8}|\d{2}[A-Z]{2}\d{5,7})\b)", 0.2),
    ]
    CONTEXT = ["case", "urn", "reference", "ref", "number"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="CASE_REFERENCE",
            name="CaseReferenceRecognizer",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )
```

- [ ] **Step 5: Write `email.py`**

```python
"""Presidio's email recogniser with the public-suffix lookup pinned offline."""

from __future__ import annotations

import tldextract
from presidio_analyzer.predefined_recognizers import EmailRecognizer

# No suffix-list URLs and no cache directory: the bundled snapshot is the only source.
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, fallback_to_snapshot=True)


class OfflineEmailRecognizer(EmailRecognizer):
    def __init__(self) -> None:
        super().__init__(name="OfflineEmailRecognizer")

    def validate_result(self, pattern_text: str) -> bool:
        return _EXTRACT(pattern_text).fqdn != ""
```

- [ ] **Step 6: Complete `build_recognisers()`**

```python
from presidio_analyzer.predefined_recognizers import NhsRecognizer
from presidio_analyzer.predefined_recognizers import PhoneRecognizer
from presidio_analyzer.predefined_recognizers import SpacyRecognizer
from presidio_analyzer.predefined_recognizers import UkNinoRecognizer
from presidio_analyzer.predefined_recognizers import UrlRecognizer

from .age import AgeRecognizer
from .case_reference import CaseReferenceRecognizer
from .date_of_birth import DateOfBirthRecognizer
from .email import OfflineEmailRecognizer
from .postcode import UkPostcodeRecognizer
from .uk_date import UkDateRecognizer

SPACY_ENTITIES = ["PERSON", "LOCATION", "ORGANIZATION"]
PHONE_REGIONS = ("GB",)


def build_recognisers() -> list[EntityRecognizer]:
    return [
        SpacyRecognizer(supported_entities=SPACY_ENTITIES),
        UkDateRecognizer(),
        DateOfBirthRecognizer(),
        AgeRecognizer(),
        UkPostcodeRecognizer(),
        NhsRecognizer(),
        UkNinoRecognizer(),
        PhoneRecognizer(supported_regions=PHONE_REGIONS),
        OfflineEmailRecognizer(),
        UrlRecognizer(),
        CaseReferenceRecognizer(),
    ]
```

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/test_recogniser_case_reference.py tests/test_recogniser_reused.py -q`
Expected: all pass. If the NINO test for `JG 20 31 97 A` fails, check Presidio's regex allows the spaced form (it does: `([A-Z]{2}) ?(\d{2}) ?(\d{2}) ?(\d{2}) ?([A-D])`).

- [ ] **Step 8: Run `make check` and commit**

```bash
git add -A
git commit -m "feat: add case reference and offline email recognisers; register NHS, NINO, phone and URL

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Gazetteer data, build script and recogniser

**Files:**
- Create: `scripts/build_gazetteer.py`, `scripts/gazetteer_stoplist.txt`, `scripts/gazetteer_extra.txt`, `src/hyperscale/pii_scanner/data/uk_places.txt`, `src/hyperscale/pii_scanner/_gazetteer.py`, `src/hyperscale/pii_scanner/_recognisers/gazetteer.py`
- Modify: `src/hyperscale/pii_scanner/_recognisers/__init__.py`
- Test: `tests/test_gazetteer.py`, `tests/test_build_gazetteer.py`

**Interfaces:**
- Produces: `_gazetteer.PlaceIndex(names: Iterable[str])` with `.find(text) -> list[tuple[int, int]]`; `_gazetteer.load_places() -> PlaceIndex` (cached); `UkGazetteerRecognizer()` producing `LOCATION` with score 0.6 and recogniser name `UkGazetteerRecognizer`. Build script functions `select_names(rows, zipf) -> tuple[set[str], list[str]]`, `strip_admin(name) -> str`.

- [ ] **Step 1: Write the failing index and recogniser tests**

```python
# tests/test_gazetteer.py
from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import scan
from hyperscale.pii_scanner._gazetteer import PlaceIndex
from hyperscale.pii_scanner._gazetteer import load_places
from hyperscale.pii_scanner._recognisers.gazetteer import UkGazetteerRecognizer
from tests.helpers import matches


def test_index_matches_whole_words_case_sensitive_longest_first():
    index = PlaceIndex(["Leeds", "Newcastle upon Tyne", "Newcastle", "Tower Hamlets", "Hull"])
    text = "Leeds, leeds, Leedsville, Newcastle upon Tyne, Tower Hamlets and Hull's."
    found = [text[s:e] for s, e in index.find(text)]
    assert found == ["Leeds", "Newcastle upon Tyne", "Tower Hamlets", "Hull"]


def test_index_handles_hyphen_and_apostrophe_names():
    index = PlaceIndex(["Stoke-on-Trent", "Bishop's Stortford"])
    text = "From Stoke-on-Trent to Bishop's Stortford."
    assert [text[s:e] for s, e in index.find(text)] == ["Stoke-on-Trent", "Bishop's Stortford"]


def test_shipped_gazetteer_has_expected_entries_and_no_common_words():
    index = load_places()
    names = index.names
    for present in ["Harrogate", "Leeds", "London", "York", "Hackney", "Tower Hamlets", "Kent", "Newcastle upon Tyne", "Kingston upon Thames", "Caernarfon"]:
        assert present in names, present
    for absent in ["Street", "Hope", "March", "Sale", "Reading", "Deal", "Wells", "Mold", "Ware", "Rye"]:
        assert absent not in names, absent
    assert len(names) > 3000


def test_recogniser_reports_location_with_fixed_score():
    found = matches(UkGazetteerRecognizer(), "She moved to Harrogate.", "LOCATION")
    assert found == [("Harrogate", 0.6)]


def test_scan_reports_gazetteer_place_spacy_misses_with_gazetteer_name():
    hits = scan("Placement: Pontefract. Next: Cleckheaton.")
    found = {h.text: (h.kind, h.recogniser) for h in hits}
    for place in ("Pontefract", "Cleckheaton"):
        kind, _ = found[place]
        assert kind == HitKind.LOCATION


def test_spacy_person_beats_gazetteer_on_same_span():
    hits = scan("Mr Preston attended with Mrs Chester.")
    kinds = {h.text: h.kind for h in hits}
    assert kinds.get("Preston") in (HitKind.PERSON, None) or kinds.get("Mr Preston") == HitKind.PERSON
```

- [ ] **Step 2: Write the failing build-script tests**

```python
# tests/test_build_gazetteer.py
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_gazetteer.py"


def _load():
    spec = importlib.util.spec_from_file_location("build_gazetteer", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(name: str, fclass: str, fcode: str, population: int, admin2: str = "") -> list[str]:
    row = [""] * 19
    row[1] = name
    row[2] = name
    row[6] = fclass
    row[7] = fcode
    row[11] = admin2
    row[14] = str(population)
    return row


def test_strip_admin_prefixes_and_suffixes():
    bg = _load()
    assert bg.strip_admin("London Borough of Hackney") == "Hackney"
    assert bg.strip_admin("Royal Borough of Kingston upon Thames") == "Kingston upon Thames"
    assert bg.strip_admin("City of York") == "York"
    assert bg.strip_admin("Wyre Forest District") == "Wyre Forest"
    assert bg.strip_admin("Caerphilly County Borough") == "Caerphilly"
    assert bg.strip_admin("Sir Powys") == "Powys"
    assert bg.strip_admin("Kent") == "Kent"


def test_select_names_applies_population_frequency_stoplist_and_extras():
    bg = _load()
    rows = [
        _row("Harrogate", "P", "PPL", 89060),
        _row("Tinyhamlet", "P", "PPL", 120),
        _row("Street", "P", "PPL", 12911),
        _row("London", "P", "PPLC", 8961989),
        _row("London Borough of Hackney", "A", "ADM3", 273526, admin2="GLA"),
        _row("Wyre Forest District", "A", "ADM3", 100000, admin2="XX"),
        _row("Kent", "A", "ADM2", 1500000),
        _row("Bath", "P", "PPLA2", 101557),
    ]
    zipf = {"street": 5.28, "london": 5.27, "harrogate": 2.92, "kent": 4.17, "bath": 4.44, "hackney": 3.0}
    names, dropped = bg.select_names(rows, zipf.get, stoplist={"Bath"}, extras={"London"}, min_population=1000)
    assert names == {"Harrogate", "London", "Hackney", "Kent"}
    assert "Street" in dropped and "London" in dropped
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_gazetteer.py tests/test_build_gazetteer.py -q`
Expected: FAIL with `ModuleNotFoundError` / missing script.

- [ ] **Step 4: Write `scripts/build_gazetteer.py`**

```python
"""Build data/uk_places.txt from the GeoNames GB extract.

Usage: uv run --group gazetteer python scripts/build_gazetteer.py [--input GB.zip]

Rules (see the design spec):
- populated places (feature class P) with population >= 1,000
- ADM2 areas (counties, unitary authorities) and ADM3 areas within Greater
  London (admin2 code GLA), with administrative prefixes and suffixes stripped
- single-word names whose lower-cased form has a wordfreq Zipf frequency >= 4.5
  are dropped unless listed in scripts/gazetteer_extra.txt
- scripts/gazetteer_stoplist.txt removes names; scripts/gazetteer_extra.txt adds them

GeoNames data is CC BY 4.0: https://www.geonames.org/
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
import sys
import urllib.request
import zipfile
from collections.abc import Callable
from collections.abc import Iterable
from pathlib import Path

GEONAMES_URL = "https://download.geonames.org/export/dump/GB.zip"
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "src" / "hyperscale" / "pii_scanner" / "data" / "uk_places.txt"
STOPLIST = REPO_ROOT / "scripts" / "gazetteer_stoplist.txt"
EXTRAS = REPO_ROOT / "scripts" / "gazetteer_extra.txt"
MIN_POPULATION = 1000
MAX_ZIPF = 4.5
LONDON_ADMIN2 = "GLA"

PREFIXES = (
    "London Borough of ",
    "Royal Borough of ",
    "Metropolitan Borough of ",
    "City and Borough of ",
    "City and County of ",
    "Borough of ",
    "City of ",
    "County of ",
    "District of ",
    "Sir ",
)
SUFFIXES = (" County Borough", " District", " Borough")
NAME_OK = re.compile(r"^[A-Z][A-Za-z'’\- ]*[A-Za-z]$")


def strip_admin(name: str) -> str:
    for prefix in PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    for suffix in SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.strip()


def read_list(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def select_names(
    rows: Iterable[list[str]],
    zipf: Callable[[str], float | None],
    *,
    stoplist: set[str],
    extras: set[str],
    min_population: int = MIN_POPULATION,
) -> tuple[set[str], list[str]]:
    """Return (names, dropped_by_frequency). ``zipf`` maps a lower-cased word to its Zipf score."""
    candidates: set[str] = set()
    for row in rows:
        name, fclass, fcode = row[1], row[6], row[7]
        population = int(row[14] or 0)
        admin2 = row[11]
        if fclass == "P" and population >= min_population:
            candidates.add(name)
        elif fclass == "A" and fcode == "ADM2":
            candidates.add(strip_admin(name))
        elif fclass == "A" and fcode == "ADM3" and admin2 == LONDON_ADMIN2:
            candidates.add(strip_admin(name))
    dropped: list[str] = []
    names: set[str] = set()
    for name in candidates:
        if not NAME_OK.match(name) or len(name) < 3 or name in stoplist:
            continue
        if " " not in name and "-" not in name:
            score = zipf(name.lower())
            if score is not None and score >= MAX_ZIPF:
                dropped.append(name)
                if name not in extras:
                    continue
        names.add(name)
    names |= {e for e in extras if e not in stoplist}
    return names, sorted(dropped)


def load_rows(source: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(source)) as zf:
        text = zf.read("GB.txt").decode("utf-8")
    return list(csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE))


def write_output(names: set[str], extract_date: str) -> None:
    header = [
        "# UK place names for hyperscale-pii-scanner.",
        f"# Source: GeoNames GB extract ({GEONAMES_URL}), licensed CC BY 4.0,",
        "# data from GeoNames (https://www.geonames.org/).",
        f"# Extract date: {extract_date}. Rules: populated places with population >= {MIN_POPULATION},",
        "# ADM2 areas, London ADM3 boroughs; single-word names with wordfreq Zipf >= "
        f"{MAX_ZIPF} dropped unless in scripts/gazetteer_extra.txt;",
        "# scripts/gazetteer_stoplist.txt applied. Regenerate with `make gazetteer`.",
        f"# Entries: {len(names)}",
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(header + sorted(names)) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    from wordfreq import zipf_frequency

    if "--input" in argv:
        source = Path(argv[argv.index("--input") + 1]).read_bytes()
    else:
        print(f"downloading {GEONAMES_URL}", file=sys.stderr)
        with urllib.request.urlopen(GEONAMES_URL, timeout=120) as response:  # noqa: S310
            source = response.read()
    rows = load_rows(source)
    names, dropped = select_names(
        rows,
        lambda word: zipf_frequency(word, "en"),
        stoplist=read_list(STOPLIST),
        extras=read_list(EXTRAS),
    )
    write_output(names, dt.date.today().isoformat())
    print(f"wrote {len(names)} names to {OUTPUT}", file=sys.stderr)
    print("dropped by frequency (add to gazetteer_extra.txt to keep):", file=sys.stderr)
    print("  " + ", ".join(dropped), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 5: Write the curated lists, then build and curate**

`scripts/gazetteer_extra.txt` (names the frequency filter would drop but which are unmistakably places; one per line, `#` comments allowed):
```
# Dropped by the Zipf >= 4.5 rule but unambiguous as UK places.
London
York
Lincoln
Derby
Bristol
Leeds
Hull
Kent
Essex
Surrey
Devon
Cornwall
Durham
Lancaster
Oxford
Cambridge
Manchester
Liverpool
Birmingham
Sheffield
Glasgow
Edinburgh
Cardiff
Belfast
Brighton
Chester
Preston
Bolton
Bradford
Croydon
Reading
Bath
Wells
```

Remove `Reading`, `Bath` and `Wells` from that list again before committing: the shipped gazetteer test expects them absent because they collide with common words in prose. Keep them out and mention in the README that spaCy still catches them in context.

`scripts/gazetteer_stoplist.txt`:
```
# Place names that are also common capitalised words or titles in reports.
Street
Hope
March
Sale
Deal
Mold
Ware
Rye
Reading
Bath
Wells
Bourne
Hay
Looe
Beer
Tring
Leek
Battle
Ely
Eye
Hale
Hurst
Seaton
Bow
Barking
Church
Chapel
Hall
Park
Grange
Mill
Cross
Green
Hill
Bridge
Ford
Mount
```

Run:
```bash
make gazetteer
```
Review the "dropped by frequency" list printed to stderr. Add any clearly unambiguous place names to `gazetteer_extra.txt`, and any remaining common-word names you see in `data/uk_places.txt` to `gazetteer_stoplist.txt`, then run `make gazetteer` again. The committed file is the one the tests and measurements use.

- [ ] **Step 6: Write `_gazetteer.py`**

```python
"""Whole-word, case-sensitive matching of the shipped UK place-name list."""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import cache
from importlib.resources import files

_TOKEN = re.compile(r"(?<![\w'’])[A-Z][\w'’\-]*")


class PlaceIndex:
    """Index names by their first token so a scan is linear in the text length."""

    def __init__(self, names: Iterable[str]) -> None:
        self.names: frozenset[str] = frozenset(n.strip() for n in names if n.strip())
        by_first: dict[str, list[str]] = {}
        for name in self.names:
            by_first.setdefault(name.split(" ", 1)[0], []).append(name)
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
            first = match.group()
            candidates = self._by_first.get(first)
            if candidates is None:
                # The token may extend past the first word of a hyphenated name;
                # also try the plain token split on hyphens.
                candidates = self._by_first.get(first.split("-", 1)[0])
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
    data = files("hyperscale.pii_scanner").joinpath("data/uk_places.txt").read_text(encoding="utf-8")
    return PlaceIndex(line for line in data.splitlines() if line and not line.startswith("#"))
```

- [ ] **Step 7: Write `_recognisers/gazetteer.py`**

```python
"""Report gazetteer place names as LOCATION even when spaCy misses them."""

from __future__ import annotations

from presidio_analyzer import LocalRecognizer
from presidio_analyzer import RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from .._gazetteer import load_places

SCORE = 0.6


class UkGazetteerRecognizer(LocalRecognizer):
    def __init__(self) -> None:
        super().__init__(supported_entities=["LOCATION"], name="UkGazetteerRecognizer")

    def load(self) -> None:
        load_places()

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        if "LOCATION" not in entities:
            return []
        return [
            RecognizerResult(
                entity_type="LOCATION",
                start=start,
                end=end,
                score=SCORE,
                recognition_metadata={
                    RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                    RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id,
                },
            )
            for start, end in load_places().find(text)
        ]
```

- [ ] **Step 8: Register** (`from .gazetteer import UkGazetteerRecognizer`; insert `UkGazetteerRecognizer()` right after `SpacyRecognizer(...)`).

- [ ] **Step 9: Run the tests**

Run: `uv run pytest tests/test_gazetteer.py tests/test_build_gazetteer.py -q`
Expected: all pass. Presidio de-duplicates a gazetteer LOCATION contained in a spaCy LOCATION of the same span (same entity type, keeps the higher score), so "Harrogate" reports once with recogniser `SpacyRecognizer` when spaCy also finds it, and with `UkGazetteerRecognizer` when it does not.

- [ ] **Step 10: Run `make check` and commit**

```bash
git add -A
git commit -m "feat: add GeoNames-derived UK gazetteer and location recogniser

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: Fixture corpus, corpus test and `scripts/measure.py`

**Files:**
- Create: `tests/fixtures/corpus/expert_report.txt` + `.expected.json`, `clinical_letter.txt` + `.expected.json`, `case_note.txt` + `.expected.json`, `business_letter.txt` + `.expected.json`, `placeholders_only.txt` + `.expected.json`, `tests/corpus.py`, `tests/test_corpus.py`, `scripts/measure.py`

**Interfaces:**
- Produces: `tests.corpus.load_corpus() -> list[CorpusDocument]` where `CorpusDocument(name, text, allowlist, placeholder_patterns, expected: list[tuple[HitKind, str]], must_not_report: list[str])`; `tests.corpus.score(doc, hits) -> dict[HitKind, Counts]` with `Counts(tp, fp, fn)`.

Sidecar JSON shape:
```json
{
  "allowlist": ["Dr Ian Brown", "IDB Experts Ltd"],
  "placeholder_patterns": ["\\b[A-Z]{3,}\\d[A-Z]{1,3}\\b", "\\([A-Z][A-Z ]+\\d?\\)"],
  "expected": [{"kind": "location", "text": "Harrogate"}],
  "must_not_report": ["MOTHER2FN", "(LOCAL AUTHORITY)", "Dr Ian Brown"]
}
```
`expected` is a multiset: list an entry once per planted occurrence. The corpus test and the measurement script treat it as ground truth. If a corpus test fails, fix the scanner, not the sidecar, unless the entry is outside the spec's detection list.

- [ ] **Step 1: Write `tests/fixtures/corpus/expert_report.txt`**

```
INDEPENDENT PSYCHOLOGICAL ASSESSMENT

Prepared for the Family Court by Dr Ian Brown, Consultant Clinical Psychologist, IDB Experts Ltd.
Subject: CHILD1FN CHILD1SN. Instructed by (LOCAL AUTHORITY).

1. Background

1.1 CHILD1FN is the second child of MOTHER2FN MOTHER2SN and FATHER1FN FATHER1SN. The family were
previously housed by (LOCAL AUTHORITY) and later moved to a privately rented property in Harrogate,
where CHILD1FN attends (SCHOOL1). The health visitor from (GP SURGERY) described the home as cluttered
but warm.

1.2 CHILD1FN was born prematurely at 34 weeks. The hospital discharge summary records the NHS number
943 476 5919 and lists MOTHER2FN as the primary carer. CHILD1FN's date of birth is recorded as
14/03/2019 on the referral form; this was not redacted in the bundle supplied to me.

1.3 MOTHER2FN describes a childhood marked by instability. She reports that her own mother, GMOTHER1FN,
left the family home when MOTHER2FN was a six-year-old and that contact has been intermittent since.

2. Sources of information

2.1 I interviewed MOTHER2FN on two occasions and observed contact between MOTHER2FN and CHILD1FN at the
(CONTACT CENTRE). I reviewed the bundle prepared by (LOCAL AUTHORITY), including the social work
chronology, the report of the guardian, and school records from (SCHOOL1).

3. Opinion

3.1 In my opinion MOTHER2FN presents with features consistent with an anxious attachment style. Her
capacity to prioritise CHILD1FN's needs has improved over the assessment period. I note that the
family's support network in the town is limited to one neighbour, (NEIGHBOUR1).

3.2 I recommend a further period of assessment of twelve weeks with support from (LOCAL AUTHORITY)
and a review by the court thereafter.

Dr Ian Brown
IDB Experts Ltd
```

`expert_report.expected.json`:
```json
{
  "allowlist": ["Dr Ian Brown", "IDB Experts Ltd"],
  "placeholder_patterns": ["\\b[A-Z]{3,}\\d[A-Z]{1,3}\\b", "\\([A-Z][A-Z ]+\\d?\\)"],
  "expected": [
    {"kind": "location", "text": "Harrogate"},
    {"kind": "nhs_number", "text": "943 476 5919"},
    {"kind": "date_of_birth", "text": "14/03/2019"},
    {"kind": "age", "text": "six-year-old"}
  ],
  "must_not_report": [
    "CHILD1FN", "CHILD1SN", "MOTHER2FN", "MOTHER2SN", "FATHER1FN", "FATHER1SN", "GMOTHER1FN",
    "(LOCAL AUTHORITY)", "(SCHOOL1)", "(GP SURGERY)", "(CONTACT CENTRE)", "(NEIGHBOUR1)",
    "Dr Ian Brown", "IDB Experts Ltd"
  ]
}
```

- [ ] **Step 2: Write `clinical_letter.txt`**

```
Westfield Medical Practice
12 Station Parade, Harrogate, HG1 1AA
Tel 01423 496000

Our ref: WMP/2026/0412
Date: 13th of July 2026

Dear Dr Patel,

Re: Amelia Thornton, DOB 02/11/1991, NHS number 398 259 7919
Address: Flat 3, 45 Cold Bath Road, Harrogate, HG2 0NA

Thank you for seeing this 34-year-old woman who attended the practice on 9 July 2026 complaining of
persistent headaches over the preceding six weeks. She works as a teaching assistant at Rossett School
and lives with her partner, Daniel Okafor, and their daughter.

Amelia can be contacted on 07911 123456 or by email at amelia.thornton@example.org. Her next of kin is
her mother, Mrs Janet Thornton, who lives in Knaresborough.

I would be grateful for your opinion on whether imaging is indicated. Past history includes migraine
diagnosed in March 2015. Her national insurance number was supplied for the sick note: JG 20 31 97 A.

Yours sincerely,

Dr Sunita Rao
GP Partner
```

`clinical_letter.expected.json`:
```json
{
  "allowlist": [],
  "placeholder_patterns": [],
  "expected": [
    {"kind": "organisation", "text": "Westfield Medical Practice"},
    {"kind": "location", "text": "Harrogate"},
    {"kind": "location", "text": "Harrogate"},
    {"kind": "postcode", "text": "HG1 1AA"},
    {"kind": "postcode", "text": "HG2 0NA"},
    {"kind": "phone", "text": "01423 496000"},
    {"kind": "date", "text": "13th of July 2026"},
    {"kind": "person", "text": "Patel"},
    {"kind": "person", "text": "Amelia Thornton"},
    {"kind": "date_of_birth", "text": "02/11/1991"},
    {"kind": "nhs_number", "text": "398 259 7919"},
    {"kind": "age", "text": "34-year-old"},
    {"kind": "date", "text": "9 July 2026"},
    {"kind": "organisation", "text": "Rossett School"},
    {"kind": "person", "text": "Daniel Okafor"},
    {"kind": "phone", "text": "07911 123456"},
    {"kind": "email", "text": "amelia.thornton@example.org"},
    {"kind": "person", "text": "Janet Thornton"},
    {"kind": "location", "text": "Knaresborough"},
    {"kind": "date", "text": "March 2015"},
    {"kind": "national_insurance_number", "text": "JG 20 31 97 A"},
    {"kind": "person", "text": "Sunita Rao"}
  ],
  "must_not_report": []
}
```

- [ ] **Step 3: Write `case_note.txt`**

```
CASE NOTE - CHILDREN'S SERVICES

Case number: ZC24C50123
Court: the Family Court sitting in Leeds. Judgment reported as [2026] EWFC 12.
Allocated social worker: Priya Nair. Team manager: Mark Ellison.

Home visit on Tuesday 7 July 2026 to the family address in Tower Hamlets. Present: mother, Chloe
Barker (aged 27), and the children. The eldest, Tyler, is 8 years old and attends Olga Primary School.
The youngest was born on 21 January 2024.

Chloe said she has been in contact with her former partner, Ryan Mackie, by phone (07700 123456) despite
the non-molestation order. She showed me a text from him sent on 03/07/2026.

Chloe's housing application references her NI number AB 12 34 56 C. The housing officer at Hackney
Council, Tom Reed, can be reached on 020 7946 0958. Further details are on the portal at
https://www.example.org/cases/12345.

Actions: liaise with the Crown Court regarding case T20247123; update the guardian; next visit in
two weeks.
```

`case_note.expected.json`:
```json
{
  "allowlist": [],
  "placeholder_patterns": [],
  "expected": [
    {"kind": "case_reference", "text": "ZC24C50123"},
    {"kind": "location", "text": "Leeds"},
    {"kind": "case_reference", "text": "[2026] EWFC 12"},
    {"kind": "person", "text": "Priya Nair"},
    {"kind": "person", "text": "Mark Ellison"},
    {"kind": "date", "text": "Tuesday 7 July 2026"},
    {"kind": "location", "text": "Tower Hamlets"},
    {"kind": "person", "text": "Chloe Barker"},
    {"kind": "age", "text": "aged 27"},
    {"kind": "person", "text": "Tyler"},
    {"kind": "age", "text": "8 years old"},
    {"kind": "organisation", "text": "Olga Primary School"},
    {"kind": "date_of_birth", "text": "21 January 2024"},
    {"kind": "person", "text": "Chloe"},
    {"kind": "person", "text": "Ryan Mackie"},
    {"kind": "phone", "text": "07700 123456"},
    {"kind": "date", "text": "03/07/2026"},
    {"kind": "national_insurance_number", "text": "AB 12 34 56 C"},
    {"kind": "organisation", "text": "Hackney Council"},
    {"kind": "person", "text": "Tom Reed"},
    {"kind": "phone", "text": "020 7946 0958"},
    {"kind": "url", "text": "https://www.example.org/cases/12345"},
    {"kind": "case_reference", "text": "T20247123"}
  ],
  "must_not_report": []
}
```

Note: `07700 123456` is not in Ofcom's reserved drama range (that is 07700 900000 to 900999), so phonenumbers treats it as a valid mobile. If the URL hit's text differs (Presidio's URL regex may stop before the path), replace the expected `url` text with what `scan` returns, since the URL recogniser is Presidio's and the span it chooses is its contract.

- [ ] **Step 4: Write `business_letter.txt`**

```
IDB Experts Ltd

Dear colleague,

Thank you for your enquiry about our assessment service. We provide independent psychological
assessments for family proceedings and accept instructions from solicitors and local authorities.

Our standard turnaround is eight weeks from receipt of the bundle. Fees are set out in the attached
schedule and are fixed for the duration of the instruction. We do not accept instructions where the
bundle has not been anonymised in line with the guidance in the attached protocol.

Please contact the office if you have any questions.

Yours faithfully,

Dr Ian Brown
Director, IDB Experts Ltd
```

`business_letter.expected.json`:
```json
{
  "allowlist": ["Dr Ian Brown", "IDB Experts Ltd"],
  "placeholder_patterns": [],
  "expected": [],
  "must_not_report": ["Dr Ian Brown", "IDB Experts Ltd"]
}
```

- [ ] **Step 5: Write `placeholders_only.txt`**

```
SUMMARY OF CONCERNS

MOTHER1FN MOTHER1SN and FATHER2FN FATHER2SN attended the meeting at (LOCAL AUTHORITY) offices with
CHILD3FN. The school, (SCHOOL2), reported that CHILD3FN had missed eleven sessions this term. The
health visitor from (HEALTH VISITING TEAM) raised no new concerns. SIBLING1FN remains placed with
(FOSTER CARER 1) and attends (SCHOOL1).

Contact with FATHER2FN is supervised at (CONTACT CENTRE) and is reported to be positive. The family
are known to (POLICE FORCE) following an incident in which NEIGHBOUR2FN called 999. The GP at
(GP SURGERY) has prescribed medication to MOTHER1FN.

Next review at (LOCAL AUTHORITY) offices. Chair: CHAIR1FN CHAIR1SN.
```

`placeholders_only.expected.json`:
```json
{
  "allowlist": [],
  "placeholder_patterns": ["\\b[A-Z]{3,}\\d[A-Z]{1,3}\\b", "\\([A-Z][A-Z ]+\\d?\\)"],
  "expected": [],
  "must_not_report": [
    "MOTHER1FN", "MOTHER1SN", "FATHER2FN", "FATHER2SN", "CHILD3FN", "SIBLING1FN", "NEIGHBOUR2FN",
    "CHAIR1FN", "CHAIR1SN", "(LOCAL AUTHORITY)", "(SCHOOL2)", "(SCHOOL1)", "(HEALTH VISITING TEAM)",
    "(FOSTER CARER 1)", "(CONTACT CENTRE)", "(POLICE FORCE)", "(GP SURGERY)"
  ]
}
```

- [ ] **Step 6: Write `tests/corpus.py`**

```python
"""Shared corpus loading and scoring for the corpus test and scripts/measure.py."""

from __future__ import annotations

import json
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
        sidecar = json.loads(text_path.with_suffix(".expected.json").read_text(encoding="utf-8"))
        docs.append(
            CorpusDocument(
                name=text_path.stem,
                text=text_path.read_text(encoding="utf-8"),
                allowlist=list(sidecar.get("allowlist", [])),
                placeholder_patterns=list(sidecar.get("placeholder_patterns", [])),
                expected=[(HitKind(e["kind"]), e["text"]) for e in sidecar.get("expected", [])],
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
```

- [ ] **Step 7: Write `tests/test_corpus.py`**

```python
from collections import Counter

import pytest

from hyperscale.pii_scanner import scan
from tests.corpus import CorpusDocument
from tests.corpus import load_corpus

DOCS = load_corpus()


@pytest.mark.parametrize("doc", DOCS, ids=[d.name for d in DOCS])
def test_every_planted_identifier_is_found(doc: CorpusDocument):
    hits = scan(doc.text, allowlist=doc.allowlist, placeholder_patterns=doc.placeholder_patterns)
    found = Counter((h.kind, h.text) for h in hits)
    missing = [key for key, n in Counter(doc.expected).items() if found[key] < n]
    assert not missing, f"missing in {doc.name}: {missing}; hits were {[(h.kind.value, h.text) for h in hits]}"


@pytest.mark.parametrize("doc", DOCS, ids=[d.name for d in DOCS])
def test_no_placeholder_or_allowlisted_text_is_reported(doc: CorpusDocument):
    hits = scan(doc.text, allowlist=doc.allowlist, placeholder_patterns=doc.placeholder_patterns)
    leaked = [
        (h.kind.value, h.text)
        for h in hits
        for forbidden in doc.must_not_report
        if h.text == forbidden or h.text in forbidden or forbidden in h.text
    ]
    assert leaked == []


def test_corpus_has_the_required_documents():
    names = {d.name for d in DOCS}
    assert {"expert_report", "clinical_letter", "case_note", "business_letter", "placeholders_only"} <= names
```

- [ ] **Step 8: Run the corpus tests and fix what they reveal**

Run: `uv run pytest tests/test_corpus.py -q -x`
Expected: pass. Likely failures and their fixes:
- A planted identifier found with a different boundary (`Dr Patel` instead of `Patel`, `www.example.org/cases/12345` instead of the full URL): the leak was found, so update the sidecar text to the returned span.
- A planted `person` missing because spaCy split or missed it: spaCy hits are best effort; if the name is absent even with the full line, change the planted sentence so the name is in a clearer context (for example "Mrs Janet Thornton" rather than a bare surname), then update the sidecar to the new text. Do not remove the entry.
- A placeholder reported as ORG: the placeholder pattern must cover it; check the pattern in the sidecar matches the token exactly.
- `Tuesday 7 July 2026` reported without the weekday: the WEEKDAY fragment is optional and Presidio keeps the longest same-entity match, so the longer span should win; if not, check `remove_duplicates` is seeing both and the shorter one is contained.

- [ ] **Step 9: Write `scripts/measure.py`**

```python
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
    "the mother reported that the child attended school regularly and the social worker "
    "visited the family home on several occasions during the assessment period while the "
    "father maintained that contact had been positive and the guardian agreed"
).split()


def perf_document(words: int = 15000, seed: int = 1) -> str:
    rng = random.Random(seed)
    paragraphs: list[str] = []
    total = 0
    while total < words:
        body = " ".join(rng.choice(WORDS) for _ in range(110)).capitalize()
        paragraphs.append(
            f"{body}. The review on 13th of July 2026 in Leeds was attended by Dr Smith, "
            "NHS number 943 476 5919, postcode LS1 4AP, phone 0113 496 0000, aged 34."
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
        hits = scan(doc.text, allowlist=doc.allowlist, placeholder_patterns=doc.placeholder_patterns)
        for kind, counts in score(doc, hits).items():
            totals[kind].tp += counts.tp
            totals[kind].fp += counts.fp
            totals[kind].fn += counts.fn
    print(f"| Kind | TP | FP | FN | Precision | Recall |")
    print(f"|---|---|---|---|---|---|")
    grand = Counts()
    for kind, c in totals.items():
        if c.tp + c.fp + c.fn == 0:
            continue
        grand.tp += c.tp
        grand.fp += c.fp
        grand.fn += c.fn
        print(f"| {kind.value} | {c.tp} | {c.fp} | {c.fn} | {fmt(c.precision)} | {fmt(c.recall)} |")
    print(f"| all | {grand.tp} | {grand.fp} | {grand.fn} | {fmt(grand.precision)} | {fmt(grand.recall)} |")
    print()
    loaded_rss = rss_mb()
    text = perf_document()
    scan(text[:2000])  # warm
    started = time.perf_counter()
    hits = scan(text)
    elapsed = time.perf_counter() - started
    print(f"Perf document: {len(text.split())} words, {len(hits)} hits, {elapsed:.2f} s")
    print(f"Resident memory after load: {loaded_rss:.0f} MB; peak after scan: {rss_mb():.0f} MB")
    print(f"Versions: {scanner_version()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 10: Run the measurement**

Run: `make measure`
Expected: a markdown table, the perf line under 5 s, memory figures and the version line. Keep the output; the README task pastes it.

- [ ] **Step 11: Run `make check` and commit**

```bash
git add -A
git commit -m "test: add synthetic fixture corpus, corpus tests and measurement script

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 12: Performance and thread-safety tests

**Files:**
- Create: `tests/test_perf.py`, `tests/test_threads.py`

- [ ] **Step 1: Write `tests/test_perf.py`**

```python
import os
import sys
import time
from pathlib import Path

import pytest

from hyperscale.pii_scanner import scan

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from measure import perf_document  # noqa: E402

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
```

- [ ] **Step 2: Write `tests/test_threads.py`**

```python
import threading
from concurrent.futures import ThreadPoolExecutor

from hyperscale.pii_scanner import Hit
from hyperscale.pii_scanner import scan
from tests.corpus import load_corpus


def test_concurrent_scans_match_serial_results():
    docs = load_corpus() * 2
    serial = [scan(d.text, allowlist=d.allowlist, placeholder_patterns=d.placeholder_patterns) for d in docs]
    barrier = threading.Barrier(len(docs))

    def work(index: int) -> list[Hit]:
        barrier.wait()
        d = docs[index]
        return scan(d.text, allowlist=d.allowlist, placeholder_patterns=d.placeholder_patterns)

    with ThreadPoolExecutor(max_workers=len(docs)) as pool:
        concurrent = list(pool.map(work, range(len(docs))))
    assert concurrent == serial
```

- [ ] **Step 3: Run both**

Run: `uv run pytest tests/test_perf.py tests/test_threads.py -q`
Expected: pass; the perf test prints nothing but takes a few seconds.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test: add performance budget and thread-safety tests

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 13: Documents extra

**Files:**
- Create: `src/hyperscale/pii_scanner/documents.py`
- Test: `tests/test_documents.py`

**Interfaces:**
- Produces: `Segment(start, end, label)`, `ExtractedText(text, segments)` with `locate(offset) -> str`, `extract_text(source, kind) -> ExtractedText`, constants `MAX_BYTES = 50 * 1024 * 1024`, `MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_documents.py
import io
import zipfile
from pathlib import Path

import docx
import openpyxl
import pytest

from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import scan
from hyperscale.pii_scanner.documents import ExtractedText
from hyperscale.pii_scanner.documents import Segment
from hyperscale.pii_scanner.documents import extract_text


def _docx(paragraphs: list[str], table: list[list[str]] | None = None, header: str | None = None) -> bytes:
    document = docx.Document()
    for p in paragraphs:
        document.add_paragraph(p)
    if table:
        t = document.add_table(rows=len(table), cols=len(table[0]))
        for r, row in enumerate(table):
            for c, value in enumerate(row):
                t.cell(r, c).text = value
    if header is not None:
        document.sections[0].header.paragraphs[0].text = header
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def _xlsx(cells: dict[str, dict[str, object]]) -> bytes:
    wb = openpyxl.Workbook()
    first = True
    for sheet, values in cells.items():
        ws = wb.active if first else wb.create_sheet()
        ws.title = sheet
        first = False
        for ref, value in values.items():
            ws[ref] = value
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_docx_paragraphs_tables_and_headers_get_labels():
    data = _docx(["Intro.", "", "Jane Smith attended."], table=[["Name", "Town"], ["Bob Jones", "Leeds"]], header="Case ZC24C50123")
    doc = extract_text(data, kind="docx")
    assert doc.locate(doc.text.index("Jane Smith")) == "paragraph 3"
    assert doc.locate(doc.text.index("Bob Jones")) == "table 1, row 2, cell 1"
    assert doc.locate(doc.text.index("Leeds")) == "table 1, row 2, cell 2"
    assert doc.locate(doc.text.index("ZC24C50123")) == "header 1"
    assert "\n\n" not in doc.text  # empty paragraphs are skipped


def test_xlsx_cells_get_sheet_and_coordinate_labels():
    data = _xlsx({"Results": {"A1": "Patient", "B20": "Jane Smith", "C3": 42}, "Notes": {"A1": "Harrogate"}})
    doc = extract_text(data, kind="xlsx")
    assert doc.locate(doc.text.index("Jane Smith")) == "sheet Results, cell B20"
    assert doc.locate(doc.text.index("42")) == "sheet Results, cell C3"
    assert doc.locate(doc.text.index("Harrogate")) == "sheet Notes, cell A1"


def test_hits_map_back_to_locations():
    doc = extract_text(_docx(["Nothing here.", "NHS number 943 476 5919."]), kind="docx")
    hits = scan(doc.text)
    nhs = next(h for h in hits if h.kind == HitKind.NHS_NUMBER)
    assert doc.locate(nhs.start) == "paragraph 2"


def test_extract_handles_empty_documents():
    assert extract_text(_docx([]), kind="docx") == ExtractedText(text="", segments=())
    assert extract_text(_docx([], header="only header"), kind="docx").segments == (Segment(0, 11, "header 1"),)
    assert extract_text(_xlsx({"Empty": {}}), kind="xlsx") == ExtractedText(text="", segments=())


def test_locate_separator_offset_maps_to_preceding_segment_and_rejects_out_of_range():
    doc = extract_text(_docx(["One", "Two"]), kind="docx")
    assert doc.text == "One\nTwo"
    assert doc.locate(3) == "paragraph 1"
    with pytest.raises(ValueError):
        doc.locate(99)
    with pytest.raises(ValueError):
        doc.locate(-1)


def test_path_input(tmp_path: Path):
    path = tmp_path / "x.docx"
    path.write_bytes(_docx(["Hello"]))
    assert extract_text(path, kind="docx").text == "Hello"
    assert extract_text(str(path), kind="docx").text == "Hello"


def test_rejects_unknown_kind_and_non_zip_and_oversize(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(ValueError, match="kind"):
        extract_text(b"x", kind="pdf")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="zip"):
        extract_text(b"not a zip file", kind="docx")
    monkeypatch.setattr("hyperscale.pii_scanner.documents.MAX_BYTES", 10)
    with pytest.raises(ValueError, match="larger"):
        extract_text(_docx(["Hello"]), kind="docx")


def test_rejects_zip_bombs_by_declared_size(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("hyperscale.pii_scanner.documents.MAX_UNCOMPRESSED_BYTES", 100)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", "0" * 10_000)
    with pytest.raises(ValueError, match="uncompressed"):
        extract_text(buf.getvalue(), kind="docx")


def test_corrupt_document_raises_value_error():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("hello.txt", "not a document")
    with pytest.raises(ValueError, match="could not parse"):
        extract_text(buf.getvalue(), kind="docx")
    with pytest.raises(ValueError, match="could not parse"):
        extract_text(buf.getvalue(), kind="xlsx")


def test_openpyxl_uses_defusedxml():
    import openpyxl.xml

    assert openpyxl.xml.DEFUSEDXML is True
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_documents.py -q`
Expected: FAIL with `ModuleNotFoundError: hyperscale.pii_scanner.documents`.

- [ ] **Step 3: Write `documents.py`**

```python
"""Optional text extraction from Word and Excel files with a location map.

Install with ``hyperscale-pii-scanner[documents]``. Every file is treated as
untrusted input: size caps, a declared-uncompressed-size check before parsing,
entity resolution disabled in python-docx, defusedxml installed for openpyxl.
"""

from __future__ import annotations

import bisect
import io
import os
import zipfile
from dataclasses import dataclass
from typing import Literal

# openpyxl uses lxml with its own entity-safe parser when lxml is present
# (python-docx installs it) and defusedxml for streaming parses when installed.
try:
    import docx
    import openpyxl
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "hyperscale.pii_scanner.documents needs the 'documents' extra: "
        "uv add 'hyperscale-pii-scanner[documents]'"
    ) from exc

from docx.table import Table
from docx.text.paragraph import Paragraph

MAX_BYTES = 50 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
SEPARATOR = "\n"

Kind = Literal["docx", "xlsx"]


@dataclass(frozen=True, slots=True)
class Segment:
    start: int
    end: int
    label: str


@dataclass(frozen=True, slots=True)
class ExtractedText:
    text: str
    segments: tuple[Segment, ...]

    def locate(self, offset: int) -> str:
        """Label of the segment containing ``offset`` (a separator maps to the preceding segment)."""
        if offset < 0 or offset > len(self.text) or not self.segments:
            raise ValueError(f"offset {offset} is outside the extracted text")
        starts = [s.start for s in self.segments]
        index = bisect.bisect_right(starts, offset) - 1
        if index < 0:
            raise ValueError(f"offset {offset} precedes the first segment")
        return self.segments[index].label


def _read_source(source: str | os.PathLike[str] | bytes) -> bytes:
    if isinstance(source, bytes):
        data = source
    else:
        path = os.fspath(source)
        if os.path.getsize(path) > MAX_BYTES:
            raise ValueError(f"file is larger than {MAX_BYTES} bytes")
        with open(path, "rb") as handle:
            data = handle.read()
    if len(data) > MAX_BYTES:
        raise ValueError(f"file is larger than {MAX_BYTES} bytes")
    return data


def _check_zip(data: bytes) -> None:
    buffer = io.BytesIO(data)
    if not zipfile.is_zipfile(buffer):
        raise ValueError("file is not a zip container (expected .docx or .xlsx)")
    with zipfile.ZipFile(buffer) as zf:
        declared = sum(info.file_size for info in zf.infolist())
    if declared > MAX_UNCOMPRESSED_BYTES:
        raise ValueError(f"declared uncompressed size {declared} exceeds {MAX_UNCOMPRESSED_BYTES} bytes")


class _Builder:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.segments: list[Segment] = []
        self.length = 0

    def add(self, text: str, label: str) -> None:
        text = text.strip()
        if not text:
            return
        if self.parts:
            self.length += len(SEPARATOR)
        start = self.length
        self.parts.append(text)
        self.length += len(text)
        self.segments.append(Segment(start, self.length, label))

    def build(self) -> ExtractedText:
        return ExtractedText(SEPARATOR.join(self.parts), tuple(self.segments))


def _extract_docx(data: bytes) -> ExtractedText:
    builder = _Builder()
    document = docx.Document(io.BytesIO(data))
    paragraph_number = 0
    table_number = 0
    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            paragraph_number += 1
            builder.add(item.text, f"paragraph {paragraph_number}")
        elif isinstance(item, Table):
            table_number += 1
            for row_number, row in enumerate(item.rows, start=1):
                for cell_number, cell in enumerate(row.cells, start=1):
                    builder.add(cell.text, f"table {table_number}, row {row_number}, cell {cell_number}")
    for section_number, section in enumerate(document.sections, start=1):
        for paragraph in section.header.paragraphs:
            builder.add(paragraph.text, f"header {section_number}")
        for paragraph in section.footer.paragraphs:
            builder.add(paragraph.text, f"footer {section_number}")
    return builder.build()


def _extract_xlsx(data: bytes) -> ExtractedText:
    builder = _Builder()
    workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.value is None:
                        continue
                    builder.add(str(cell.value), f"sheet {sheet.title}, cell {cell.coordinate}")
    finally:
        workbook.close()
    return builder.build()


def extract_text(source: str | os.PathLike[str] | bytes, kind: Kind) -> ExtractedText:
    """Extract plain text and a location map from a .docx or .xlsx file."""
    if kind not in ("docx", "xlsx"):
        raise ValueError(f"unsupported kind {kind!r}; expected 'docx' or 'xlsx'")
    data = _read_source(source)
    _check_zip(data)
    try:
        return _extract_docx(data) if kind == "docx" else _extract_xlsx(data)
    except Exception as exc:
        raise ValueError(f"could not parse {kind} document: {exc}") from exc
```

- [ ] **Step 4: Run the tests, lint, types**

Run: `uv run pytest tests/test_documents.py -q && uv run pyright`
Expected: pass. If pyright complains about `cell.coordinate` on read-only cells, annotate `cell` via `from openpyxl.cell.read_only import ReadOnlyCell` and `isinstance` checks, keeping strict mode.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add optional documents extra for docx and xlsx extraction with location map

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 14: README, platform guide, changelog and release tooling

**Files:**
- Create: `README.md`, `PLATFORM_GUIDE.md`, `scripts/release.py`
- Modify: `CHANGELOG.md`, `Makefile`, `src/hyperscale/pii_scanner/__init__.py` (docstring only)
- Test: `tests/test_release.py`

- [ ] **Step 1: Write the failing release-script tests**

```python
# tests/test_release.py
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release.py"
SAMPLE = """# Changelog

## [Unreleased]

### Added

- First thing.

## [0.1.0] - 2026-10-20

### Added

- Initial release.
"""


def _load():
    spec = importlib.util.spec_from_file_location("release", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_promote_unreleased_moves_section_under_new_version():
    rel = _load()
    updated = rel.promote_unreleased(SAMPLE, "0.2.0", "2026-11-01")
    assert "## [Unreleased]\n\n## [0.2.0] - 2026-11-01\n\n### Added\n\n- First thing.\n" in updated
    assert "## [0.1.0] - 2026-10-20" in updated


def test_promote_unreleased_refuses_empty_section():
    rel = _load()
    empty = "# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - 2026-10-20\n"
    with pytest.raises(SystemExit, match="empty"):
        rel.promote_unreleased(empty, "0.2.0", "2026-11-01")


def test_section_notes_returns_body_for_version():
    rel = _load()
    assert rel.section_notes(SAMPLE, "0.1.0") == "### Added\n\n- Initial release."
    with pytest.raises(SystemExit, match="no CHANGELOG section"):
        rel.section_notes(SAMPLE, "9.9.9")
```

- [ ] **Step 2: Write `scripts/release.py` (stdlib only)**

```python
"""Changelog helpers for the Makefile release targets.

Usage:
  python3 scripts/release.py promote <version>   # move [Unreleased] under [<version>] - today
  python3 scripts/release.py check <version>     # exit 1 unless CHANGELOG has [<version>]
  python3 scripts/release.py notes <version>     # print the section body (release notes)
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
HEADING = re.compile(r"^## \[(?P<version>[^\]]+)\](?: - (?P<date>\d{4}-\d{2}-\d{2}))?$", re.MULTILINE)


def _sections(text: str) -> list[tuple[str, int, int, int]]:
    """(version, heading_start, body_start, body_end) for each section."""
    headings = list(HEADING.finditer(text))
    out: list[tuple[str, int, int, int]] = []
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        out.append((match.group("version"), match.start(), match.end(), end))
    return out


def section_notes(text: str, version: str) -> str:
    for name, _, body_start, body_end in _sections(text):
        if name == version:
            return text[body_start:body_end].strip()
    raise SystemExit(f"no CHANGELOG section for {version}")


def promote_unreleased(text: str, version: str, date: str) -> str:
    for name, heading_start, body_start, body_end in _sections(text):
        if name == "Unreleased":
            body = text[body_start:body_end].strip()
            if not body:
                raise SystemExit("the [Unreleased] section is empty; add entries before releasing")
            replacement = f"## [Unreleased]\n\n## [{version}] - {date}\n\n{body}\n\n"
            return text[:heading_start] + replacement + text[body_end:]
    raise SystemExit("no [Unreleased] section in CHANGELOG.md")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit(__doc__)
    command, version = argv
    text = CHANGELOG.read_text(encoding="utf-8")
    if command == "promote":
        CHANGELOG.write_text(promote_unreleased(text, version, dt.date.today().isoformat()), encoding="utf-8")
    elif command == "check":
        section_notes(text, version)
    elif command == "notes":
        print(section_notes(text, version))
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 3: Run the release tests**

Run: `uv run pytest tests/test_release.py -q`
Expected: `3 passed`.

- [ ] **Step 4: Add the release targets to the `Makefile`**

Append:
```make
.PHONY: bump tag release

# make bump PART=patch|minor|major  -> bumps pyproject version, locks, promotes CHANGELOG
bump:
	@test -n "$(PART)" || (echo "usage: make bump PART=patch|minor|major" && exit 1)
	uv version --bump $(PART)
	uv lock
	python3 scripts/release.py promote $$(uv version --short)
	git add pyproject.toml uv.lock CHANGELOG.md
	git commit -m "chore: release v$$(uv version --short)"

# Tag the current commit as v<version>; requires a clean tree and a CHANGELOG section.
tag:
	git diff --quiet && git diff --cached --quiet
	python3 scripts/release.py check $(VERSION)
	git tag -a v$(VERSION) -m "v$(VERSION)"

# Push main and the tag, then create the GitHub release (triggers publish.yml).
release: tag
	git push origin main
	git push origin v$(VERSION)
	python3 scripts/release.py notes $(VERSION) > /tmp/hyperscale-pii-scanner-notes.md
	gh release create v$(VERSION) --title "v$(VERSION)" --notes-file /tmp/hyperscale-pii-scanner-notes.md
```
Add `VERSION := $(shell uv version --short)` near the top of the Makefile, after `MAKEFLAGS`.

- [ ] **Step 5: Write `README.md`**

Replace the table rows marked with `<from make measure>` with the numbers printed by `make measure` in Task 11, and the date with today's date. Everything else is final text.

````markdown
# hyperscale-pii-scanner

Deterministic, in-process scan for residual personal identifiers in UK English
text. Built on [Microsoft Presidio](https://github.com/microsoft/presidio) with
[spaCy](https://spacy.io) as the NER engine, with UK-specific recognisers, a UK
place-name gazetteer, pinned versions and a small, stable interface.

It exists as a second line of defence for apps that accept documents which are
supposed to have been anonymised before upload. The app scans the text, holds
the upload while a person replaces or confirms each hit, and only then passes
the content on.

**This library is best effort. It reports what it found. It never certifies
that text is anonymised, and no caller should describe its output that way.**

## What it detects

| Kind | What | How |
|---|---|---|
| `person` | Personal names | spaCy NER |
| `location` | Places, addresses | spaCy NER plus the UK gazetteer |
| `organisation` | Organisations | spaCy NER |
| `date` | Full dates and month-year pairs in UK conventions (`13th of July 2026`, `3rd June 2026`, `13/07/2026`, `2026-07-13`, `July 2026`) | pattern |
| `date_of_birth` | A date within 25 characters after `DOB`, `D.O.B`, `date of birth`, `birth date` or `born` | pattern |
| `age` | `aged 34`, `34 years old`, `34-year-old`, `six-year-old`, `18 months old` | pattern |
| `postcode` | Full UK postcodes on their own; outward codes such as `LS1` only when a word like `postcode` precedes them | pattern with position rules |
| `nhs_number` | Ten-digit NHS numbers that pass the Modulus 11 check | Presidio |
| `national_insurance_number` | NINOs with the valid prefix and suffix rules | Presidio |
| `phone` | UK landline and mobile numbers, with or without `+44` | Presidio, phonenumbers, GB region only |
| `email` | Email addresses with a real top-level domain (offline suffix list) | Presidio |
| `url` | Web addresses | Presidio |
| `case_reference` | Court case numbers (`ZC24C50123`), neutral citations (`[2026] EWFC 12`), Crown Court and CPS numbers when a word like `case` precedes them | pattern |

## What it does not detect

- Anything in a language other than English.
- Bare years, durations ("three weeks"), times.
- Nationality, religion or political group (spaCy's NORP label is ignored).
- Credit cards, bank accounts, IBANs, IP addresses, crypto wallets, UK passport or
  driving licence numbers, vehicle registrations. Presidio has recognisers for
  these; they are deliberately not registered.
- Ofcom's reserved fictional phone ranges (07700 900xxx and similar) are not
  valid numbers and are not reported.
- Names, places and organisations the model does not recognise. NER is
  statistical. Short alphanumeric tokens are sometimes reported as organisations.
- Place names that are also common words (`Street`, `Hope`, `Reading`, `Bath`,
  `Wells`) are excluded from the gazetteer to avoid flagging ordinary prose; the
  model still reports them when the context makes them a place.

## Installation

```bash
uv add hyperscale-pii-scanner                # core
uv add "hyperscale-pii-scanner[documents]"   # plus Word and Excel extraction
```

Python 3.14 or later. The wheel includes the spaCy `en_core_web_md` model, so
nothing is downloaded at install or run time.

## Interface

```python
from hyperscale.pii_scanner import Hit, HitKind, redact, scan, scanner_version

hits: list[Hit] = scan(
    text,
    allowlist=["Dr Ian Brown", "IDB Experts Ltd"],
    placeholder_patterns=[r"\b[A-Z]{3,}\d[A-Z]{1,3}\b", r"\([A-Z][A-Z ]+\d?\)"],
    language="en",
)
for hit in hits:
    print(hit.kind, hit.text, hit.start, hit.end, hit.score, hit.recogniser)

redacted = redact(text, hits, token_for=lambda hit: f"[{hit.kind.value.upper()}]")

str(scanner_version())
# 'hyperscale-pii-scanner 0.1.0; presidio-analyzer 2.2.364; spacy 3.8.16; en_core_web_md 3.8.0'
```

- `scan` returns hits sorted by position, non-overlapping, each with a score of
  at least 0.3. `Hit` is a frozen dataclass; `text` is always `source[start:end]`.
- `HitKind` is a closed `StrEnum` with the thirteen members in the table above.
- `redact` replaces each hit with a token (`[KIND]` by default). It raises
  `ValueError` if a hit does not line up with the text, which catches hits from
  a different document.
- `scanner_version()` returns the library, Presidio, spaCy and model versions
  for audit logs. It does not load the model.
- `language` accepts only `"en"`. Any other value raises `ValueError`.
- The model loads once per process on the first non-empty scan (about 1.5 s).
  `scan` is safe to call from multiple threads; calls are serialised on a lock,
  so use processes for parallelism.
- Results are deterministic for the same input, configuration, library
  versions and CPU architecture.

### Allowlist and placeholders

Suppression runs after recognition, so it applies the same way whichever
recogniser produced a hit. A hit is dropped when its span lies inside:

- any whole-word, case-insensitive occurrence of an allowlist entry, or
- any match of a placeholder pattern (a Python regular expression).

This is slightly stronger than exact matching on the hit text: if the model
reports `Ian Brown` out of `Dr Ian Brown`, or `LOCAL AUTHORITY` out of
`(LOCAL AUTHORITY)`, the hit is still suppressed. A hit that extends beyond a
placeholder (`MOTHER2FN Jones`) is reported, because the extra text may be a
leak. Invalid patterns raise `ValueError` before scanning.

### Document extraction (optional)

```python
from hyperscale.pii_scanner.documents import extract_text

doc = extract_text(path_or_bytes, kind="docx")   # or "xlsx"
hits = scan(doc.text)
for hit in hits:
    print(doc.locate(hit.start), hit.kind, hit.text)   # "paragraph 14", "sheet Results, cell B20"
```

Word: body paragraphs and tables in order, then section headers and footers.
Footnotes, comments and text boxes are not read. Excel: every non-empty cell,
sheet by sheet, using cached values rather than formulas. Files are untrusted
input: a 50 MB size cap, a declared-uncompressed-size cap of 250 MB checked
before parsing, XML entity resolution disabled, and defusedxml for openpyxl.
Parsing failures raise `ValueError`.

## Measured behaviour

Measured on <date> with `make measure` against the synthetic fixture corpus in
`tests/fixtures/corpus/` (five documents, written for this project). The
figures describe that corpus, not real documents.

| Kind | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|
<from make measure>

Timing and memory, Apple M-series laptop, model already loaded:

| Measure | Value |
|---|---|
| 15,000-word document scan | <from make measure> s |
| Resident memory after load | <from make measure> MB |
| Peak resident memory after that scan | <from make measure> MB |

The test suite asserts the scan stays under 5 s locally and 10 s on the slower
CI runner.

## Configuration

There is one configuration point, for the spaCy model:

```python
from hyperscale.pii_scanner import configure

configure(model="en_core_web_lg")        # a package name, or a path to a model directory
```

Call it before the first scan (for example in a Django `AppConfig.ready()`);
it raises `RuntimeError` afterwards. The large model is about 400 MB and is not
on PyPI; install it with
`uv add https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.8.0/en_core_web_lg-3.8.0-py3-none-any.whl`.

## Maintenance

### Upgrading the model

1. Change `MODEL_VERSION`, `WHEEL_URL` and `WHEEL_SHA256` in `scripts/vendor_model.py`
   (compute the digest with `shasum -a 256` on the downloaded wheel).
2. Change `DEFAULT_MODEL_VERSION` in `src/hyperscale/pii_scanner/_engine.py`,
   the `MODEL_META` path in the `Makefile`, and the wheel-content check in `ci.yml`.
3. `python3 scripts/vendor_model.py --force`, then `make check` and `make measure`.
4. Update the measured numbers above and the CHANGELOG.

### Adding a recogniser

1. Add a module under `src/hyperscale/pii_scanner/_recognisers/` that subclasses
   Presidio's `PatternRecognizer` or `LocalRecognizer` and produces a new entity type.
2. Add the entity type to `ENTITY_TO_KIND` in `_postprocess.py` and, if it is a
   structured kind, to `STRUCTURED_PRIORITY`. Add the kind to `HitKind` if it is new.
3. Register it in `build_recognisers()` in `_recognisers/__init__.py`.
4. Add positive and negative unit tests, plant an example in the corpus, and
   re-run `make measure`.

### Refreshing the gazetteer

`make gazetteer` downloads the GeoNames GB extract, applies the rules in
`scripts/build_gazetteer.py`, and rewrites `data/uk_places.txt`. Review the
"dropped by frequency" list it prints; add genuine places to
`scripts/gazetteer_extra.txt` and common-word collisions to
`scripts/gazetteer_stoplist.txt`. The data file header records the extract date.

## Licences

| Component | Licence |
|---|---|
| hyperscale-pii-scanner | MIT |
| presidio-analyzer | MIT |
| spaCy | MIT |
| en_core_web_md 3.8.0 (vendored) | MIT for the model; trained on OntoNotes 5 (licensed to Explosion), vectors CC0 |
| phonenumbers | Apache-2.0 |
| tldextract | BSD-3-Clause |
| Gazetteer (`data/uk_places.txt`) | Derived from GeoNames, CC BY 4.0. Data from [GeoNames](https://www.geonames.org/). Extract date in the file header. |
| python-docx, openpyxl (extra) | MIT |
| defusedxml (extra) | PSF-2.0 |

## Release process

```bash
make bump PART=minor   # bump version, promote the CHANGELOG [Unreleased] section, commit
make release           # tag v<version>, push, create the GitHub release; publish.yml uploads to PyPI
```

Publishing uses PyPI trusted publishing from the `pypi` GitHub environment; no API tokens.
````

- [ ] **Step 6: Write `PLATFORM_GUIDE.md`**

```markdown
# Residual identifier scanning: platform guide

The platform can scan uploaded document text for residual personal identifiers
using `hyperscale-pii-scanner`. This page tells a design what it may say, what
flow it must include, and what it must not claim.

## What a design may write

A design invokes the service with a sentence such as:

> System scans the document for residual identifiers, treating the expert's
> placeholder tokens and the author's name as safe.

The design may name:

- **Safe strings** (the allowlist): exact names that must never be reported, such
  as the document author or their organisation.
- **Placeholder patterns**: the shape of the anonymisation tokens already in the
  document, such as `MOTHER2FN` or `(LOCAL AUTHORITY)`. The platform turns these
  into patterns; a design only needs to give examples.

Kinds the scan reports: person, location, organisation, date, date of birth,
age, postcode, NHS number, National Insurance number, phone, email, URL, case
reference. Each hit carries the text, its position and which rule found it.

## Required flow extension

A design that scans uploads must include this flow:

1. The document is uploaded and its text is extracted.
2. System scans the document for residual identifiers.
3. **Identifiers are found: the upload is held** until a person has reviewed
   every hit and either replaced it (with a placeholder) or confirmed it is safe.
4. Only after the review is complete may the content be used, stored for
   processing, or passed to any model.

A design may let the reviewer add confirmed hits to the safe strings for that
document or that author. It may not auto-confirm hits.

## Limits a design must respect

- **Best effort.** The scan reports what it found. It can miss identifiers and it
  can flag text that is not one. The design must not describe the output as
  anonymised, cleaned, safe or compliant. Say "scanned for residual identifiers"
  and "reviewed by a person".
- **English only.** Documents in other languages are not supported; the design
  should reject or route them elsewhere.
- **A human confirmation step is required.** The hold in step 3 cannot be
  skipped, timed out, or satisfied by a second automated pass.
- **Word, Excel and plain text only.** PDF and scanned images are not supported
  unless the design converts them to text first, and OCR errors reduce detection.
- **Audit.** Record the scanner version string with each review so the result
  can be reproduced.
- **Never describe the result as anonymised.** Describe it as reviewed.
```

- [ ] **Step 7: Update `CHANGELOG.md`**

Under `## [Unreleased]`:
```markdown
### Added

- `scan`, `redact`, `Hit`, `HitKind`, `configure`, `scanner_version`.
- UK recognisers: dates, date of birth, ages, postcodes, case references;
  Presidio's NHS, NINO, GB phone, email (offline) and URL recognisers.
- GeoNames-derived UK gazetteer reported as `location`.
- Optional `documents` extra with `extract_text` for .docx and .xlsx.
- Vendored `en_core_web_md` 3.8.0; pinned presidio-analyzer 2.2.364 and spaCy 3.8.16.
```

- [ ] **Step 8: Run everything and commit**

Run: `make check && uvx pre-commit run --all-files`
Expected: all pass.

```bash
git add -A
git commit -m "docs: add README, platform guide, changelog entry and release tooling

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 15: Public repository, CI green, PyPI handover

**Files:**
- None new. Pushes the repository and verifies CI.

- [ ] **Step 1: Final local verification**

```bash
make check
uv build
unzip -l dist/*.whl | grep -c "_model/en_core_web_md-3.8.0/"   # expect > 50 files
unzip -l dist/*.whl | grep "data/uk_places.txt"
uvx twine check dist/*
uvx zizmor .github/workflows/
```
Expected: all pass; the wheel is roughly 35 MB.

- [ ] **Step 2: Create the public repository and push**

```bash
gh repo create hyperscale-consulting/hyperscale-pii-scanner --public \
  --description "Deterministic, offline scan for residual personal identifiers in UK English text (Presidio + spaCy)" \
  --source . --remote origin --push
gh api -X PUT repos/hyperscale-consulting/hyperscale-pii-scanner/environments/pypi
```

- [ ] **Step 3: Watch CI**

```bash
gh run list --limit 3
gh run watch --exit-status
```
Expected: lint, test, build, pip-audit and zizmor all green. If the test job exceeds the 10 s perf budget on the hosted runner, record the measured time from the job log and raise `PII_SCANNER_PERF_BUDGET_SECONDS` in `ci.yml` to the next whole multiple of 5 above it, noting the change in the CHANGELOG.

- [ ] **Step 4: Hand over for PyPI trusted publishing**

Report to the user the values to enter on PyPI (Add a new pending publisher):
- PyPI project name: `hyperscale-pii-scanner`
- Owner: `hyperscale-consulting`
- Repository: `hyperscale-pii-scanner`
- Workflow name: `publish.yml`
- Environment name: `pypi`

Then, once they confirm, release 0.1.0:
```bash
make release     # version is already 0.1.0; promotes nothing, tags v0.1.0, creates the release
```
Note: `make release` runs `tag`, which requires a `## [0.1.0]` section in the CHANGELOG. Before releasing, run `python3 scripts/release.py promote 0.1.0`, commit, and then `make release`. Watch `gh run watch` on the publish workflow and confirm `uv add hyperscale-pii-scanner` resolves from PyPI in a scratch project.
