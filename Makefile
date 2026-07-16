.PHONY: setup format lint typecheck test smoke check

setup:
	uv sync --dev --frozen

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

check:
	uv run --frozen ruff format --check .
	uv run --frozen ruff check .
	uv run --frozen mypy src tests
	uv run --frozen pytest
	uv run --frozen agentic-tutorial smoke
