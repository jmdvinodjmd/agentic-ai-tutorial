# Planner-executor

Create a finite plan, then execute its steps under a shared budget.

```mermaid
flowchart LR
  Planner --> Plan --> Executor --> Result
```

Run: `uv run python patterns/planner_executor/run.py`.

Use case: understandable multi-step work. Limitation: a poor plan constrains later execution.
