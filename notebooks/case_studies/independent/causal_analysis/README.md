# Causal analysis

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/case_studies/independent/causal_analysis/langgraph.ipynb)

This standalone LangGraph case study examines the observational association
between diabetes-medication changes and 30-day readmission using causal
discovery, constrained model review, DoWhy estimation and refutation, and
EconML heterogeneous-effect estimation.

The notebook supports `mock`, `local` and `api`. On Colab, use `mock` or `api`;
`local` requires the GGUF model file and llama.cpp environment described by the
repository's local-model guide. The notebook automatically installs its causal
packages and clones the repository source on a fresh Colab runtime.

Its final evaluation section reports component, trajectory, task, robustness,
efficiency and required-human-intervention checks. It also exposes the same
five-key `evaluation` result used by the matched case studies.

Its output is exploratory and assumption-dependent, not a clinical treatment
recommendation. The source dataset was designed for prediction and does not
contain every likely confounder.
