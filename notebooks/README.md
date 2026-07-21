# Notebook-first learning path

The notebooks are the tutorial: prompts, state, decisions, execution boundaries,
traces, stopping rules, evaluations and limitations are visible in each file.

## Patterns

- [Plain Python](patterns/plain_python_patterns.ipynb)
- [LangGraph](patterns/langgraph_patterns.ipynb)
- [CrewAI Flow](patterns/crewai_patterns.ipynb)
- [OpenAI Agents SDK](patterns/openai_agents_patterns.ipynb)

Each implements prompt chaining, routing, parallelisation, ReAct, planner–executor,
critic–reviser and orchestrator–worker over matched fixtures and acceptance checks.

## Case studies

| Case | Plain Python | LangGraph | CrewAI | OpenAI Agents |
|---|---|---|---|---|
| Research assistant | [open](case_studies/research_assistant/plain_python.ipynb) | [open](case_studies/research_assistant/langgraph.ipynb) | [open](case_studies/research_assistant/crewai.ipynb) | [open](case_studies/research_assistant/openai_agents.ipynb) |
| Data analysis | [open](case_studies/data_analysis_assistant/plain_python.ipynb) | [open](case_studies/data_analysis_assistant/langgraph.ipynb) | [open](case_studies/data_analysis_assistant/crewai.ipynb) | [open](case_studies/data_analysis_assistant/openai_agents.ipynb) |
| Simulated service | [open](case_studies/service_assistant/plain_python.ipynb) | [open](case_studies/service_assistant/langgraph.ipynb) | [open](case_studies/service_assistant/crewai.ipynb) | [open](case_studies/service_assistant/openai_agents.ipynb) |

All notebooks default to versioned mock decisions, run top-to-bottom without
credentials and finish with component, trajectory, task, safety and repeated-run
evaluation. Framework extras are installed only for the corresponding notebook.
