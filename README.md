# Agentic AI Tutorial

Teaching repository and reproducible research artefact for *A Practical Tutorial on Agentic AI*.

The repository provides a framework-independent execution foundation, deterministic offline examples, compact execution-pattern demonstrations and a matched research-assistant comparison.

## Learning path

Follow the [complete learning path](docs/learning_path.md) in order:

1. basic model invocation → tools → explicit state;
2. planning → retained context → critique → bounded tracing;
3. exact-action human approval;
4. execution patterns;
5. the common research-assistant case study;
6. matched framework implementations and comparison.

System components define *what the system contains*. Execution patterns define *how those components exchange control*. Framework abstractions provide alternative ways to express the same orchestration. The [glossary](docs/glossary.md) fixes the terminology used throughout.

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

The matched [CrewAI implementation](case_study/crewai/README.md) demonstrates functionally separated specialist assignments using a bounded sequential Flow.

The matched [OpenAI Agents SDK implementation](case_study/openai_agents/README.md) uses SDK agents, tools, handoffs, context and guardrails while excluding the autonomous `Runner` from the controlled comparison.

The [deterministic evaluation harness](evaluation/README.md) defines shared outcome, trajectory and resource metrics. The [matched comparison](evaluation/comparison/README.md) explains and reproduces the four-way experiment. The [safety policy](docs/safety.md) and [controlled failures](case_study/failures/README.md) demonstrate least-privilege execution and explicit failure boundaries.

## Execution modes

Deterministic offline mock execution is the project default and the only mode used for the matched comparison. Strict replay reuses versioned canonical request-response recordings and fails if a request changes. Live execution is never required for core tutorials or tests.

An [optional local-model mode](docs/local_model.md) runs a separately downloaded GGUF model through llama.cpp without a cloud API. It never replaces or silently falls back to mock or replay.

Cloud providers remain future optional adapters. They must implement the same `ModelClient` contract and cannot replace mock or replay as the reproducible default.

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

Check public documentation structure, links and documented commands with:

```bash
uv run python scripts/check_docs.py
```

## Licence

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for the full terms.
