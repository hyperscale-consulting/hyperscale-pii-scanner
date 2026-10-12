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
