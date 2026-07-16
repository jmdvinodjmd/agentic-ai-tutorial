.PHONY: setup setup-all format lint typecheck test smoke docs notebooks reproduce audit check

setup:
	uv sync --dev --frozen

setup-all:
	uv sync --dev --all-extras --frozen

format:
	uv run --frozen ruff format .

lint:
	uv run --frozen ruff check .

typecheck:
	uv run --frozen mypy src tests

test:
	uv run --frozen pytest

smoke:
	uv run --frozen agentic-tutorial smoke

docs:
	uv run --frozen python scripts/check_docs.py

notebooks:
	uv run --frozen python scripts/check_notebooks.py --execute

reproduce:
	uv run --frozen python scripts/check_reproducibility.py

audit:
	uv run --frozen python scripts/audit_public.py

check:
	uv run --frozen ruff format --check .
	uv run --frozen ruff check .
	uv run --frozen mypy src tests
	uv run --frozen pytest
	uv run --frozen agentic-tutorial smoke
	uv run --frozen python scripts/check_docs.py
	uv run --frozen python scripts/check_notebooks.py --execute
	uv run --frozen python scripts/check_reproducibility.py
	uv run --frozen python scripts/audit_public.py
