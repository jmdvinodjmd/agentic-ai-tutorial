# Compatibility

This table distinguishes completed local validation from configured continuous integration. It does not claim unobserved platforms.

| Area | Locked or supported value | Validation status |
|---|---|---|
| Python | 3.11 | Tested locally on macOS arm64; Ubuntu CI configured |
| Core | Pydantic 2.x, locked by `uv.lock` | Core-only fresh installation tested |
| LangGraph | 1.2.9 | Separate extra and case-study smoke tested locally |
| CrewAI | 1.15.2 | Separate extra and case-study smoke tested locally |
| OpenAI Agents SDK | 0.17.8 | Separate extra and case-study smoke tested locally |
| Local runtime | llama-cpp-python 0.3.34; Qwen3-0.6B GGUF metadata | Fake runtime tested; real model not downloaded or run |
| Modes | mock, replay, optional local model | Mock and replay tested; local configuration tested without weights |
| Operating systems | macOS and Linux target; Windows best effort | macOS tested; Linux awaits the first CI run; Windows untested |

Core installation does not install any framework or llama.cpp dependency. Install optional extras separately:

```bash
uv sync --dev --extra langgraph --frozen
uv sync --dev --extra crewai --frozen
uv sync --dev --extra openai-agents --frozen
uv sync --dev --extra local-llama-cpp --frozen
```

Use `uv sync --dev --all-extras --frozen` only for the complete integration suite. Framework versions are reviewed deliberately with the lock file; the project does not automatically chase latest releases.
