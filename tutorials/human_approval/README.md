# Human approval and resumption

A simulated submission action is checkpointed before execution. Approval is scoped to the exact call and arguments; rejection never executes it.

Interactive demonstration:

```bash
uv run python tutorials/human_approval/run.py
```

Deterministic modes:

```bash
uv run python -m agentic_tutorial.education approval --decision approve
uv run python -m agentic_tutorial.education approval --decision reject
uv run python -m agentic_tutorial.education approval --decision revise --revised-title "Checked revision"
```

All effects remain in memory. Checkpoints and canonical human-decision events are written beneath `outputs/runs/approval-demo/`.
