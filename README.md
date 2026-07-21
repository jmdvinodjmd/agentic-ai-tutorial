# Agentic AI Tutorial

Notebook-first companion to *A Practical Tutorial on Agentic AI*. It is a
teaching resource, not a reusable agent framework: prompts, decisions, graphs,
crews, handoffs, tool boundaries, loops, stopping conditions, traces, fault
handling, evaluation and safety decisions stay visible in the notebooks.

## Set-up and execution modes

Python 3.11 and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync --dev --frozen
MODEL_PROVIDER=mock uv run pytest
```

The default `mock` provider is deterministic, offline and used by CI. Optional
framework environments are installed independently:

```bash
uv sync --dev --extra langgraph --frozen
uv sync --dev --extra crewai --frozen
uv sync --dev --extra openai-agents --frozen
```

`MODEL_PROVIDER=gemini` uses
[`gemini-2.5-flash-lite`](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite)
by default, is available on the documented
[free tier](https://ai.google.dev/gemini-api/docs/pricing), and reads only
`GEMINI_API_KEY`. `MODEL_PROVIDER=local` uses llama.cpp and requires a separately
downloaded GGUF path in `AGENTIC_TUTORIAL_LOCAL_MODEL_PATH`; weights are never
downloaded by tests or notebooks. See [local model status](models/local/README.md).

## Notebook map

| Tutorial material | Plain Python | LangGraph | CrewAI | OpenAI Agents |
|---|---|---|---|---|
| Seven patterns | [notebook](notebooks/patterns/plain_python_patterns.ipynb) | [notebook](notebooks/patterns/langgraph_patterns.ipynb) | [notebook](notebooks/patterns/crewai_patterns.ipynb) | [notebook](notebooks/patterns/openai_agents_patterns.ipynb) |
| Research assistant | [notebook](notebooks/case_studies/research_assistant/plain_python.ipynb) | [notebook](notebooks/case_studies/research_assistant/langgraph.ipynb) | [notebook](notebooks/case_studies/research_assistant/crewai.ipynb) | [notebook](notebooks/case_studies/research_assistant/openai_agents.ipynb) |
| Data-analysis assistant | [notebook](notebooks/case_studies/data_analysis_assistant/plain_python.ipynb) | [notebook](notebooks/case_studies/data_analysis_assistant/langgraph.ipynb) | [notebook](notebooks/case_studies/data_analysis_assistant/crewai.ipynb) | [notebook](notebooks/case_studies/data_analysis_assistant/openai_agents.ipynb) |
| Simulated service assistant | [notebook](notebooks/case_studies/service_assistant/plain_python.ipynb) | [notebook](notebooks/case_studies/service_assistant/langgraph.ipynb) | [notebook](notebooks/case_studies/service_assistant/crewai.ipynb) | [notebook](notebooks/case_studies/service_assistant/openai_agents.ipynb) |

Every notebook contains its own Open in Colab badge. The
[notebook guide](notebooks/README.md) describes the matched learning path.

### Colab links

- Patterns: [plain Python](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/patterns/plain_python_patterns.ipynb), [LangGraph](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/patterns/langgraph_patterns.ipynb), [CrewAI](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/patterns/crewai_patterns.ipynb), [OpenAI Agents](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/patterns/openai_agents_patterns.ipynb).
- Research assistant: [plain Python](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/case_studies/research_assistant/plain_python.ipynb), [LangGraph](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/case_studies/research_assistant/langgraph.ipynb), [CrewAI](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/case_studies/research_assistant/crewai.ipynb), [OpenAI Agents](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/case_studies/research_assistant/openai_agents.ipynb).
- Data analysis: [plain Python](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/case_studies/data_analysis_assistant/plain_python.ipynb), [LangGraph](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/case_studies/data_analysis_assistant/langgraph.ipynb), [CrewAI](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/case_studies/data_analysis_assistant/crewai.ipynb), [OpenAI Agents](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/case_studies/data_analysis_assistant/openai_agents.ipynb).
- Simulated service: [plain Python](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/case_studies/service_assistant/plain_python.ipynb), [LangGraph](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/case_studies/service_assistant/langgraph.ipynb), [CrewAI](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/case_studies/service_assistant/crewai.ipynb), [OpenAI Agents](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/feature/notebook-rebuild/notebooks/case_studies/service_assistant/openai_agents.ipynb).

## Paper-to-notebook map

- Agent components and seven orchestration patterns → the four pattern notebooks.
- Evidence-grounded research and claim-evidence ledgers → research-assistant row.
- Tool-mediated deterministic computation → data-analysis row.
- Permissions, approvals, effects and recovery → simulated-service row.
- Evaluation, traces, budgets and stopping → final evaluation section of every notebook.
- Prompt injection, provenance, unsafe code and least privilege → case-specific safety checks.

## Reproducibility and testing

Inputs and scripted decisions are versioned under `data/`; schemas, provider
adapters, tools, canonical traces, metrics and safety primitives live under
`src/agentic_tutorial/`. Full orchestration does not. Mock notebooks are executed
twice and compared for equality.

```bash
make check
make setup-all                 # optional: install all framework/local extras
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest -q tests/test_notebook_mock_execution.py
```

CI runs core/plain notebooks without credentials and each framework in a clean,
separate optional-dependency job. Gemini and real local-model qualification are
optional integration checks and are not required in CI.

After exporting `GEMINI_API_KEY`, run Gemini's opt-in 8/8 qualification with:

```bash
uv run pytest -q tests/test_optional_gemini_qualification.py
```

The local-Qwen download, checksum and qualification commands are in the
[local model guide](models/local/README.md). Both live checks use explicit fault
injection for the malformed-response recovery probe; neither stores credentials
or downloads model weights.

## Limitations

- Fixtures and datasets are deliberately small and cannot establish external or causal validity.
- Mock runs test orchestration and safeguards, not real-model semantic quality.
- CrewAI and OpenAI Agents carry more dependency/runtime overhead than plain Python.
- The Qwen local candidate must pass the documented 8/8 qualification suite on the target laptop before it is advertised as selected.
- The service environment is simulated; it is not a durable transaction system.

## Licence

Apache License 2.0. See [LICENSE](LICENSE).
