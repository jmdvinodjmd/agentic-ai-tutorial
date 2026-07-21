# Research assistant

Matched household-food-waste evidence synthesis in
[plain Python](plain_python.ipynb), [LangGraph](langgraph.ipynb),
[CrewAI](crewai.ipynb) and [OpenAI Agents](openai_agents.ipynb).

All four use the same bounded catalogue and decisions, isolate indirect prompt
injection, preserve a claim-evidence ledger, report conflict and provenance,
validate citations, critique once and abstain when support is insufficient.

## Model selection

The first configuration cell in every case-study notebook accepts `mock`,
`local`, or `api`; the notebook value is authoritative. For Gemini, set
`MODEL_PROVIDER = "api"` and run the cell. If `GEMINI_API_KEY` is unavailable,
the notebook requests it with hidden input. Paste the key into the prompt shown
by Jupyter or VS Code and press Enter; submitting an empty prompt stops before
any API request.

With `SAVE_API_CREDENTIAL = True`, the notebook writes
the key to `.private/gemini_api_key`, which is excluded by `.gitignore` and is
created with user-only file permissions. This is a local plaintext convenience,
not encrypted secret storage; keep `SAVE_API_CREDENTIAL = False` on shared
machines and shut down the kernel when finished.
