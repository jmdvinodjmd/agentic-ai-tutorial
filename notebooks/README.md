# Notebook-first learning path

The notebooks are the tutorial: prompts, state, decisions, execution boundaries,
traces, stopping rules, evaluations and limitations are visible in each file.

From the repository root, install and launch the complete local notebook
environment with:

```bash
make setup-notebooks
make notebooks
```

Python 3.11 and `uv` are required. The notebooks default to the deterministic
mock provider, so this setup needs no API credentials or model download. When
opening a notebook directly in an editor, select
`Python 3.11 (agentic-ai-tutorial)` as its kernel.

## Patterns

- [Plain Python](patterns/plain_python_patterns.ipynb)
- [LangGraph](patterns/langgraph_patterns.ipynb)
- [CrewAI Flow](patterns/crewai_patterns.ipynb)
- [OpenAI Agents SDK](patterns/openai_agents_patterns.ipynb)

Each implements prompt chaining, routing, parallelisation, ReAct, planner–executor,
critic–reviser and orchestrator–worker over matched fixtures and acceptance checks.
Pattern notebooks intentionally keep the deterministic mock model so framework
comparisons remain reproducible.

## Case studies

| Case | Plain Python | LangGraph | CrewAI | OpenAI Agents |
|---|---|---|---|---|
| Research assistant | [open](case_studies/research_assistant/plain_python.ipynb) | [open](case_studies/research_assistant/langgraph.ipynb) | [open](case_studies/research_assistant/crewai.ipynb) | [open](case_studies/research_assistant/openai_agents.ipynb) |
| Data analysis | [open](case_studies/data_analysis_assistant/plain_python.ipynb) | [open](case_studies/data_analysis_assistant/langgraph.ipynb) | [open](case_studies/data_analysis_assistant/crewai.ipynb) | [open](case_studies/data_analysis_assistant/openai_agents.ipynb) |
| Simulated service | [open](case_studies/service_assistant/plain_python.ipynb) | [open](case_studies/service_assistant/langgraph.ipynb) | [open](case_studies/service_assistant/crewai.ipynb) | [open](case_studies/service_assistant/openai_agents.ipynb) |

Case studies that do not need a four-framework comparison live in the
[independent case-study catalogue](case_studies/independent/). Each case owns
its notebooks, documentation and additional dependency setup. Adding another
independent case therefore requires only a new case directory, not edits to
this table or the common project environment. See the
[case-study contribution convention](case_studies/README.md).

Case-study notebooks begin with `MODEL_PROVIDER = "mock"  # mock | local | api`.
Change this one value and use **Restart Kernel and Run All**. `local` uses the
lightweight Qwen model in `models/local`; `api` uses Gemini and requests a key
through hidden notebook input when the ignored local credential file is absent.
Real providers run the workflow once; mock additionally checks repeatability.
