.PHONY: setup setup-all setup-notebooks notebooks format lint typecheck test check

setup:
	uv sync --dev --frozen

setup-all:
	uv sync --dev --all-extras --frozen

setup-notebooks:
	uv sync --group notebooks --extra langgraph --extra crewai --extra openai-agents --frozen
	uv run --frozen --group notebooks --extra langgraph --extra crewai --extra openai-agents python -m ipykernel install --user --name agentic-ai-tutorial --display-name "Python 3.11 (agentic-ai-tutorial)"

notebooks:
	uv run --frozen --group notebooks --extra langgraph --extra crewai --extra openai-agents jupyter lab notebooks

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
