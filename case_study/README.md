# Reproducible research-assistant case study

This case study asks a narrow research question, searches a small synthetic local catalogue, extracts attributable evidence, synthesises a concise answer and validates its provenance. It is a teaching and comparison task, not a systematic review.

The version 1 fixture centrally fixes prompts, tool permissions, budgets, stopping rules, expected answers and scoring annotations for four variants:

- a standard evidence-grounded answer;
- insufficient evidence;
- a question requiring clarification;
- recovery from one controlled catalogue failure.

All catalogue text is original synthetic material covered by the repository licence. Default execution is offline and requires no credentials. Generated traces, checkpoints, manifests and answers are written beneath `outputs/runs/`.

The plain-Python command is documented in [plain_python/README.md](plain_python/README.md).

The matched LangGraph command is documented in [langgraph/README.md](langgraph/README.md).

The matched CrewAI command is documented in [crewai/README.md](crewai/README.md).
