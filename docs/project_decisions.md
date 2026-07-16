# Project Decisions and Deferred Choices

This file records decisions that should not be reinvented by a coding model.

## Decisions fixed now

| Area | Decision |
|---|---|
| Repository purpose | Teaching repository and reproducible artefact for **A Practical Tutorial on Agentic AI** |
| Main case study | Narrow, offline-capable research assistant using fixed fixtures |
| Reference implementation | Plain Python |
| Principal frameworks | LangGraph, CrewAI and OpenAI Agents SDK |
| Fourth framework | Optional and deferred |
| Python | 3.11 |
| Environment manager | `uv` |
| Package name | `agentic_tutorial` |
| Package layout | `src/agentic_tutorial/` |
| Schema library | Pydantic v2 |
| Test framework | pytest |
| Lint and formatting | Ruff |
| Type checking | mypy |
| Default execution | Deterministic offline mock |
| Secondary offline execution | Recorded replay |
| Live execution | Optional provider adapter |
| Documentation language | UK English |
| Tutorial tools | Read-only or simulated by default |
| Framework comparison | Same tasks, prompts, tools, budgets, outputs and metrics |
| Code in paper | Concise skeletons only; full code in repository |

## Recommended repository-level choices

These defaults may be changed deliberately, but Codex must not choose alternatives without justification.

| Area | Recommendation |
|---|---|
| CLI | Standard-library `argparse` initially |
| Documentation diagrams | Mermaid source |
| CI | GitHub Actions |
| Licence | MIT, subject to the author's confirmation |
| Supported systems | macOS and Linux first; Windows best effort |
| Generated run outputs | `outputs/runs/<run_id>/` and ignored by Git unless committed fixtures |
| Offline fixtures | JSON or JSONL under version-controlled fixture directories |
| Configuration | Typed configuration object plus environment variables only in provider construction |
| Notebook use | Supplementary only; all core functionality must be importable and testable as Python modules |

## Decisions that can be deferred

### First live model provider

This is not needed for T00 to T03 or the core offline implementation. Select it before T04.

Criteria:

- accessible to students;
- structured-output and tool-call support;
- stable official Python SDK;
- usage reporting where available;
- optional installation;
- no effect on canonical shared interfaces.

The user should choose the provider. Codex must not silently select one.

### Exact live model identifiers

Do not freeze these globally because model names and availability change. Configure them through environment variables or configuration files and record the value in run manifests.

### Fourth framework

Defer until LangGraph, CrewAI and OpenAI Agents SDK implementations are complete. Add a fourth only if it provides a distinct abstraction and can be compared fairly.

### Licence

MIT is recommended for a teaching repository, but confirm before public release.

### Archival release

Decide later whether to archive releases through Zenodo and mint a DOI for the paper artefact.

## Questions that do not block initial development

- Which journal will receive the tutorial paper?
- Which examples will appear in the final manuscript rather than only in the repository?
- Whether a graphical user interface will ever be added. It is currently outside scope.
- Whether live web search will be included. It is currently outside the default offline case study.

## Hard exclusions unless explicitly reconsidered

- autonomous systematic review;
- generic chatbot interface;
- mandatory vector database;
- mandatory paid API;
- arbitrary shell execution by an LLM;
- side-effecting tools without approval;
- framework-specific copies of shared task logic;
- ranking frameworks by code length alone;
- presenting multi-agent systems as inherently superior.
