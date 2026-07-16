# Orchestrator-worker

## Purpose

Assign functionally different tasks to workers with distinct tool permissions.

## Architecture

```mermaid
flowchart TD
  Orchestrator --> Researcher[Catalogue permission]
  Orchestrator --> Analyst[Calculator permission]
  Researcher --> Aggregate
  Analyst --> Aggregate
```

## Run

```bash
uv run python patterns/orchestrator_worker/run.py
```

## Expected output

The researcher returns catalogue evidence, the analyst returns a calculation and the orchestrator aggregates both canonical artefacts.

## Concept introduced

Specialists differ through tasks and least-privilege tools, not names alone.

## Limitations

Coordination adds events and failure paths; additional workers are not inherently better.

## Next step

Combine the components and patterns in the [common case study](../../case_study/README.md).
