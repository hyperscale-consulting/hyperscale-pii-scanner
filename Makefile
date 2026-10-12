SHELL := bash -eu -o pipefail
MAKEFLAGS += --warn-undefined-variable
VERSION := $(shell uv version --short)
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
