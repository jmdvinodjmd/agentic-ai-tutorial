# Contributing

Contributions should preserve the repository's teaching sequence and matched-comparison contract.

## Development set-up

Install Python 3.11 and `uv`, then choose either the core environment or all optional framework extras:

```bash
uv sync --dev --frozen
uv sync --dev --all-extras --frozen
```

Keep prompts and orchestration visible in notebooks. Shared schemas, tools,
provider adapters, trace contracts, evaluation metrics, safety primitives and
fixtures belong in `src/agentic_tutorial/`. New iterative flows must be bounded,
deterministic mock tests remain the default, and consequential actions require
exact-action approval.

Before opening a change, run:

```bash
make check
git diff --check
```

Update public documentation and tests with behaviour changes. Do not commit credentials, generated runs, model weights, caches, machine paths or private planning material. Please use UK English in documentation and comments.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report security concerns through the private process in [SECURITY.md](SECURITY.md), not a public issue.
