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
| `date` | Full dates and month-year pairs in UK conventions (`13th of July 2026`, `3rd June 2026`, `13/07/2026`, `13/7/26`, `13.07.2026`, `2026-07-13`, `July 2026`). A dotted date needs a four-digit year, so `6.2.10` is a paragraph reference, not a date | pattern |
| `date_of_birth` | A date within 25 characters after `DOB`, `D.O.B`, `date of birth`, `birth date` or `born`; here a dotted two-digit year (`DOB 14.3.19`) is accepted | pattern |
| `age` | `aged 34`, `34 years old`, `34-year-old`, `six-year-old`, `18 months old` | pattern |
| `postcode` | Full UK postcodes on their own; outward codes such as `LS1` only when a word like `postcode` precedes them | pattern with position rules |
| `nhs_number` | Ten-digit NHS numbers that pass the Modulus 11 check | Presidio |
| `national_insurance_number` | NINOs with the valid prefix and suffix rules | pattern |
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
  statistical. Role titles and title-case phrases are sometimes reported as
  organisations; a bare surname in a salutation is sometimes missed.
- Organisations written as a short all-caps acronym (`NHS`, `CAMHS`, `BBC`),
  and organisations that stand alone on a short line without a word such as
  `School`, `Council`, `Trust` or `Ltd` in them. Both shapes are dropped on
  purpose; see "Organisation noise" below.
- Place names that are also common words (`Street`, `Hope`, `Reading`, `Bath`,
  `Wells`) or common personal names (`Keith`, `Barry`) are excluded from the
  gazetteer to avoid flagging ordinary prose; the model still reports them when
  the context makes them a place.

## Installation

```bash
uv add hyperscale-pii-scanner                # core
uv add "hyperscale-pii-scanner[documents]"   # plus Word and Excel extraction
```

Python 3.14 or later. The wheel includes the spaCy `en_core_web_md` model, so
nothing is downloaded at install or run time.

## Interface

```python
from hyperscale.pii_scanner import (
    Hit,
    HitKind,
    placeholder_patterns_from_examples,
    redact,
    scan,
    scanner_version,
)

hits: list[Hit] = scan(
    text,
    allowlist=["Dr Ian Brown", "IDB Experts Ltd"],
    placeholder_patterns=placeholder_patterns_from_examples(
        ["MOTHER2FN", "(LOCAL AUTHORITY)", "(SCHOOL1)"]
    ),
    kinds=set(HitKind) - {HitKind.ORGANISATION},  # optional; default is every kind
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
- `allowlist` and `placeholder_patterns` must be iterables of strings; passing a
  single string raises `TypeError` rather than silently iterating its characters.
- `kinds` limits which kinds are reported (members of `HitKind` or their string
  values). An excluded kind behaves as if its recogniser had not run, so it
  cannot hide an overlapping hit of a kept kind: with `organisation` excluded,
  the gazetteer `Harrogate` under a model span `Harrogate, HG1` still appears.
  An unknown value raises `ValueError`; an empty set returns no hits.
- `placeholder_patterns_from_examples` turns example tokens into patterns, one
  per shape: a run of capitals, lowercase letters, digits or whitespace in the
  example matches any run of that class and everything else matches literally.
  `MOTHER2FN` also covers `FATHER1SN`; `(LOCAL AUTHORITY)` also covers
  `(GP SURGERY)` but not `(SCHOOL1)`, which needs its own example.
- The model loads once per process on the first non-empty scan (about 1.5 s).
  `scan` is safe to call from multiple threads; calls are serialised on a lock,
  so use processes for parallelism.
- Results are deterministic for the same input, configuration, library
  versions and CPU architecture.

### How overlapping hits are resolved

Presidio can return several results for one span (an NHS number also matches
as a phone number; the model may label a town as an organisation). The
library keeps one hit per span: a structured kind (date of birth, NHS number,
NINO, postcode, case reference, email, URL, phone, age, date, in that order)
beats a model kind; otherwise the longer span wins, then the higher score. An
exact gazetteer match of a UK place name outranks a same-span model label.

Before that, a model span that runs across a line break (a header glued to the
first word of the next line) is split into one span per line.

### Organisation noise

On real reports the model labels headings, test names and acronyms as
organisations far more often than it finds a real one. Two shapes are dropped
before overlap resolution:

- an all-caps span of six letters or fewer (`FSIQ`, `GAI`, `NHS`, `GP`), while
  longer ones (`CAFCASS`) and mixed spans (`WISC-V`) are kept;
- a span that is a whole line of six words or fewer in a multi-line text
  (`Background Information`, `Verbal Comprehension`), unless a word in it names
  an organisation type (`Practice`, `School`, `Council`, `Trust`, `Hospital`,
  `Ltd`, `Surgery`, `Court` and similar), so a letterhead line such as
  `Westfield Medical Practice` is still reported.

Callers who find the remaining organisation hits unhelpful can leave the kind
out with `kinds=`.

### Allowlist and placeholders

Suppression runs after recognition, so it applies the same way whichever
recogniser produced a hit. The library finds every whole-word,
case-insensitive occurrence of each allowlist entry and every match of each
placeholder pattern (a Python regular expression). A hit that touches one of
those spans is dropped when every token containing a capital letter or a digit
lies inside such a span. Honorifics (`Mr`, `Mrs`, `Ms`, `Miss`, `Mx`, `Dr`,
`Prof`) are neutral, like lowercase joining words.

In practice: `Ian Brown` reported out of `Dr Ian Brown` is dropped, `Ms
MOTHER2SN` is dropped, `LOCAL AUTHORITY` out of `(LOCAL AUTHORITY)` is dropped,
and a model span that glued several placeholders together with "and" is
dropped. A hit that extends beyond a placeholder with a capitalised word
(`MOTHER2FN Jones`) is reported, because the extra text may be a leak. Invalid
patterns raise `ValueError` before scanning.

### Document extraction (optional)

```python
from hyperscale.pii_scanner.documents import extract_text

doc = extract_text(path_or_bytes, kind="docx")  # or "xlsx"
hits = scan(doc.text)
for hit in hits:
    print(
        doc.locate(hit.start), hit.kind, hit.text
    )  # "paragraph 14", "sheet Results, cell B20"
```

Word: every paragraph in the body in document order, including paragraphs
inside tables, nested tables and content controls (labelled by their innermost
table, row and cell), then each section's headers and footers, including
first-page and even-page variants and tables inside them. A header linked to
the previous section is read once. Footnotes, endnotes, comments and text
boxes are not read. Excel: every non-empty cell,
sheet by sheet, using cached values rather than formulas. Files are untrusted
input: a 50 MB size cap, a declared-uncompressed-size cap of 250 MB checked
before parsing, XML entity resolution disabled in python-docx, an entity-safe
parser plus defusedxml in openpyxl. Parsing failures raise `ValueError`.

## Measured behaviour

Measured on 2026-10-13 with `make measure` against the synthetic fixture corpus
in `tests/fixtures/corpus/` (five documents, written for this project). The
figures describe that corpus, not real documents. On real reports,
organisation is the noisiest kind by a wide margin even after the
organisation-noise rules above.

| Kind | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|
| person | 12 | 2 | 0 | 0.86 | 1.00 |
| location | 6 | 1 | 0 | 0.86 | 1.00 |
| organisation | 4 | 2 | 0 | 0.67 | 1.00 |
| date | 5 | 0 | 0 | 1.00 | 1.00 |
| date_of_birth | 3 | 0 | 0 | 1.00 | 1.00 |
| age | 4 | 0 | 0 | 1.00 | 1.00 |
| postcode | 2 | 0 | 0 | 1.00 | 1.00 |
| nhs_number | 2 | 0 | 0 | 1.00 | 1.00 |
| national_insurance_number | 2 | 0 | 0 | 1.00 | 1.00 |
| phone | 4 | 0 | 0 | 1.00 | 1.00 |
| email | 1 | 0 | 0 | 1.00 | 1.00 |
| url | 1 | 0 | 0 | 1.00 | 1.00 |
| case_reference | 3 | 0 | 0 | 1.00 | 1.00 |
| all | 49 | 5 | 0 | 0.91 | 1.00 |

The false positives are all model (spaCy) labels: "the Family Court" and "the
Crown Court" as organisations, a first name as a location, and the author's
role glued to an allowlisted organisation. Pattern kinds produced no false
positives on this corpus.

Timing and memory, Apple M-series laptop, model already loaded:

| Measure | Value |
|---|---|
| 16,008-word document scan | 2.4 s |
| Resident memory after load | 423 MB |
| Peak resident memory after that scan | 812 MB |

The test suite asserts the scan stays under 5 s locally and 10 s on the slower
CI runner.

The model is loaded once per process, not per thread. A multi-worker web
server (gunicorn, uvicorn workers, Celery prefork) loads one copy per worker,
so budget roughly 450 MB resident per worker plus 400 MB of headroom for the
worker that is scanning, or run scans in a dedicated small pool of workers.

Scan time grows with the number of hits and, for spaCy's tokeniser, with
pathological punctuation runs (thousands of consecutive brackets). Scans
serialise on one lock per process, so cap upload sizes in the calling app and
scan large spreadsheets sheet by sheet rather than as one text.

## Configuration

There is one configuration point, for the spaCy model:

```python
from hyperscale.pii_scanner import configure

configure(model="en_core_web_lg")  # a package name, or a path to a model directory
```

Call it before the first scan (for example in a Django `AppConfig.ready()`);
it raises `RuntimeError` afterwards. A package name that is not installed
raises `RuntimeError` at the first scan; the library never downloads a model. The large model is about 400 MB and is not
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
   Presidio compiles patterns case-insensitively; wrap case-sensitive patterns in
   `(?-i:...)`.
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
