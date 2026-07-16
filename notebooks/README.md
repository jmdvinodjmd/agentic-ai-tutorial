# Teaching notebooks

The notebooks are supplementary teaching views over importable, tested package code. They use deterministic mock data, require no credentials or model download, and write transient run artefacts only to ignored repository-relative paths.

1. [`01_components_walkthrough.ipynb`](01_components_walkthrough.ipynb) moves from model invocation through tools, explicit state, planning, retained context, critique, bounded tracing and human approval.
2. [`02_execution_patterns.ipynb`](02_execution_patterns.ipynb) executes the six documented orchestration-pattern groups.
3. [`03_framework_comparison.ipynb`](03_framework_comparison.ipynb) explores the committed matched-comparison snapshot, deterministic outcomes, framework events and fairness caveats.

Validate and execute every code cell without a notebook server:

```bash
uv run python scripts/check_notebooks.py --execute
```

The comparison notebook loads the committed snapshot for short classroom execution. Reproduce the experiment through the command in the [comparison guide](../evaluation/comparison/README.md). Outputs and execution counts are deliberately cleared in version control.
