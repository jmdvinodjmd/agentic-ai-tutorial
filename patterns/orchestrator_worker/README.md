# Orchestrator-worker

Assign functionally different tasks to workers with distinct tool permissions.

```mermaid
flowchart TD
  Orchestrator --> Researcher[catalogue permission]
  Orchestrator --> Analyst[calculator permission]
  Researcher --> Aggregate
  Analyst --> Aggregate
```

Run: `uv run python patterns/orchestrator_worker/run.py`.

Use case: least-privilege specialisation. Limitation: coordination adds calls and failure paths.
