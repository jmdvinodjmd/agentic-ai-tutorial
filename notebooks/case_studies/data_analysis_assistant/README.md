# Data-analysis assistant

Matched implementations: [plain Python](plain_python.ipynb),
[LangGraph](langgraph.ipynb), [CrewAI](crewai.ipynb) and
[OpenAI Agents](openai_agents.ipynb).

The case study follows six matched stages:

`inspect_data → select_analysis → validate_request → execute_analysis → validate_result → report`

The user sets `ANALYSIS_QUESTION` and `MODEL_PROVIDER` near the beginning of each
notebook. The model selects a typed allowlisted analysis and writes the report,
but it never supplies executable code or numeric results. Deterministic Python
validates columns, computes the aggregation, checks a versioned oracle and
records dataset provenance.

The CrewAI implementation uses native `Agent`, `Task` and `Crew` abstractions;
LangGraph expresses the stages as graph nodes; OpenAI Agents uses typed
`Agent`/`Runner` calls. Use **Restart Kernel and Run All** after changing the
provider.
