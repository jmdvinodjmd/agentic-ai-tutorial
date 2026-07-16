# Basic model invocation

Introduces one canonical offline model request and response. Unlike the repository smoke check, this invokes the shared model interface; tools and state are excluded.

```bash
uv run python tutorials/basic_model/run.py
```

Expected: `{"answer": "Paper paper-001 is relevant.", "concept": "model invocation"}`.
