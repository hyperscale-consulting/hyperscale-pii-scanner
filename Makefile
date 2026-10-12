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
