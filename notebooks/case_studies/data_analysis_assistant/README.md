# Data-analysis assistant

Matched implementations: [plain Python](plain_python.ipynb),
[LangGraph](langgraph.ipynb), [CrewAI](crewai.ipynb) and
[OpenAI Agents](openai_agents.ipynb).

The LLM selects a typed allowlisted analysis but never supplies executable code
or numeric results. Python validates columns, computes the aggregation, checks a
versioned oracle and records dataset provenance.

Each notebook's first code cell selects `mock`, `local` (Qwen), or `api`
(Gemini). Change `MODEL_PROVIDER`, then use **Restart Kernel and Run All**; no
terminal command is required after the notebook environment has been installed.
