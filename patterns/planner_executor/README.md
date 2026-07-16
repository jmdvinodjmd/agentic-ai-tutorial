# Planner-executor

## Purpose

Create a finite plan, then execute its steps under one shared budget.

## Architecture

```mermaid
flowchart LR
  Planner --> Plan --> Executor --> Result
```

## Run

```bash
uv run python patterns/planner_executor/run.py
```

## Expected output

The command prints the fixed plan and the ordered results of its bounded execution.

## Concept introduced

Planner and executor are functional stages with different responsibilities, not merely role labels.

## Limitations

A poor plan constrains later execution unless bounded replanning is added deliberately.

## Next step

Add bounded feedback in [critic-reviser](../critic_reviser/README.md).
