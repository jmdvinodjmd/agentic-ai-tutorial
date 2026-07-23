# Case studies

Case studies are organised in two groups:

- The existing `research_assistant`, `data_analysis_assistant` and
  `service_assistant` folders are matched framework comparisons.
- [`independent/`](independent/) contains case studies that need only one
  suitable implementation.

## Adding an independent case study

Create `independent/<case_slug>/` with:

- a `README.md` explaining the question, implementation, runtime and limits;
- one or more clearly named notebooks;
- notebook-local setup for dependencies not already provided by the common
  repository environment; and
- component, trajectory, task, safety and repeatability evaluations exposed
  through the standard five-key `evaluation` object;
- an Open in Colab badge whose URL matches the notebook path.

No central case-study table needs updating. GitHub automatically lists every
folder below `independent/`, making that directory the extensible catalogue.
Only add a case to the matched framework tables when its purpose is explicitly
to compare frameworks.
