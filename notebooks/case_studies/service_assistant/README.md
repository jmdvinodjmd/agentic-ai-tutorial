# Simulated service assistant

Matched implementations: [plain Python](plain_python.ipynb),
[LangGraph](langgraph.ipynb), [CrewAI](crewai.ipynb) and
[OpenAI Agents](openai_agents.ipynb).

The case study follows seven matched stages:

`inspect_state → propose_action → authorise_action → checkpoint → execute_action → verify_effect → confirm`

The user sets `SERVICE_REQUEST`, the exact approved action and `MODEL_PROVIDER`
near the beginning of each notebook. The model may propose and confirm, but
deterministic Python owns approval, execution, checkpoint/resume and duplicate
suppression. All effects are local and simulated.

The CrewAI implementation uses native `Agent`, `Task` and `Crew` abstractions;
LangGraph expresses the stages as graph nodes; OpenAI Agents uses typed
`Agent`/`Runner` calls. Use **Restart Kernel and Run All** after changing the
provider.
