.PHONY: setup setup-all format lint typecheck test check

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

check:
	uv run --frozen ruff format --check .
	uv run --frozen ruff check .
	uv run --frozen mypy src tests
	uv run --frozen pytest
