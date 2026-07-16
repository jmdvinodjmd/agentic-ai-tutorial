# Agentic AI Tutorial

Teaching repository and reproducible research artefact for *A Practical Tutorial on Agentic AI*.

The repository is currently at foundation stage. It provides an installable Python package and a deterministic offline smoke command, but no agent, provider, tool or framework implementation yet.

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

`make check` runs formatting verification, linting, static type checking, tests and the offline smoke check. The commands are CI-ready; the full framework matrix and release automation are deferred to T24.

## Execution modes

Deterministic offline mock execution is the project default. The shared model layer also supports strict replay of versioned canonical JSONL fixtures. Runnable agent tutorials will be added by later tickets, and optional live-provider execution remains deferred. Live execution will never be required for core tutorials or tests.

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
