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
