# Agentic AI Tutorial

Teaching repository and reproducible research artefact for *A Practical Tutorial on Agentic AI*.

The repository provides a framework-independent execution foundation, deterministic offline examples and compact execution-pattern demonstrations.

## Requirements

- Python 3.11
- [uv](https://docs.astral.sh/uv/)

## Set-up

```bash
uv sync --dev --frozen
```

## Offline smoke check

No credentials or internet connection are required after set-up:

```bash
uv run agentic-tutorial smoke
```

Expected output:

```json
{"mode": "offline", "status": "ok"}
```

CLI help is available with:

```bash
uv run agentic-tutorial --help
```

## Development checks

```bash
make format
make lint
make typecheck
make test
make smoke
make check
```

`make check` runs formatting verification, linting, static type checking, tests and the offline smoke check.

## Runnable examples

The [progressive tutorials](tutorials/README.md) introduce model calls, tools, state, planning, retained context, critique, bounded execution and human approval one concept at a time.

The [execution patterns](patterns/README.md) demonstrate six common orchestration flows. All examples run offline with deterministic local fixtures.

The [research-assistant case study](case_study/README.md) provides a versioned common task and a complete framework-independent reference implementation.

The matched [LangGraph implementation](case_study/langgraph/README.md) expresses the same task as explicit graph nodes and conditional edges while preserving the common contracts and evaluator.

The [deterministic evaluation harness](evaluation/README.md) defines shared outcome, trajectory and resource metrics. The [safety policy](docs/safety.md) and [controlled failures](case_study/failures/README.md) demonstrate least-privilege execution and explicit failure boundaries.

## Execution modes

Deterministic offline mock execution is the project default. The shared model layer also supports strict replay of versioned canonical JSONL fixtures. Live execution is never required for core tutorials or tests.

An [optional local-model mode](docs/local_model.md) runs a separately downloaded GGUF model through llama.cpp without a cloud API. It never replaces or silently falls back to mock or replay.

## Repository layout

- `src/agentic_tutorial/`: installable shared package;
- `tutorials/`: progressive teaching examples;
- `patterns/`: grouped execution-pattern examples;
- `frameworks/`: reusable framework-specific orchestration only;
- `case_study/`: runnable case-study entry points, configuration and documentation;
- `evaluation/`: experiment configuration and reports;
- `tests/`: automated tests and versioned fixtures;
- `notebooks/`: supplementary notebooks only;
- `outputs/runs/`: generated run artefacts, ignored unless explicitly declared fixtures;
- `docs/`: project specifications and documentation.

## Licence

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for the full terms.
