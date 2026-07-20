# Agentic AI Tutorial

Notebook-first companion to *A Practical Tutorial on Agentic AI*. Important
prompts, state, model decisions, routing, loops, stopping conditions, traces,
evaluation and safety decisions remain visible in the notebooks. Shared Python
modules contain only genuine infrastructure such as provider adapters, schemas,
tools, traces, evaluation contracts, safety primitives and fixtures.

## Current milestone

The preservation branches and first rebuild milestone are complete. The first
[plain-Python patterns notebook](notebooks/patterns/plain_python_patterns.ipynb)
contains a runnable prompt-chaining example. The remaining patterns and matched
case-study notebooks will be added incrementally after review.

## Set-up

Requires Python 3.11 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --dev --frozen
```

Mock execution is deterministic and requires no credentials:

```bash
export MODEL_PROVIDER=mock
uv run pytest
```

Optional providers use `MODEL_PROVIDER=local` or `MODEL_PROVIDER=gemini`.
Gemini reads only `GEMINI_API_KEY`; local inference reads
`AGENTIC_TUTORIAL_LOCAL_MODEL_PATH`. Neither is required by CI.

## Structure

- `notebooks/patterns/` — matched pattern notebooks, beginning with plain Python;
- `notebooks/case_studies/` — research, data-analysis and simulated-service cases;
- `src/agentic_tutorial/` — shared infrastructure only;
- `data/` — small versioned fixtures for the three cases;
- `tests/` — contract, qualification and mock notebook tests;
- `models/` — local-model provenance and qualification metadata.

The complete notebook map, paper-section map, Colab links and reproducibility
instructions will be added after the replacement notebooks are implemented.

## Licence

Apache License 2.0. See [LICENSE](LICENSE).
