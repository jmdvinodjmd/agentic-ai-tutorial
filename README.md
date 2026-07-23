# Agentic AI Tutorial

Notebook-first companion to *A Practical Tutorial on Agentic AI*. It is a
teaching resource, not a reusable agent framework: prompts, decisions, graphs,
crews, handoffs, tool boundaries, loops, stopping conditions, traces, fault
handling, evaluation and safety decisions stay visible in the notebooks.

## Set-up and execution modes

### Shared requirements

All approaches require Git, Python 3.11 and
[`uv`](https://docs.astral.sh/uv/). Clone the repository, enter its directory,
then install Jupyter and all three orchestration frameworks:

```bash
make setup-notebooks
make notebooks
```

The first command creates `.venv`, installs JupyterLab, LangGraph, CrewAI and
OpenAI Agents, and registers the `Python 3.11 (agentic-ai-tutorial)` kernel. The
second opens JupyterLab. Select that kernel if you open a notebook directly in
VS Code or another editor.

Pattern notebooks intentionally use only the deterministic mock model. Every
case-study notebook has this configuration near the top:

```python
MODEL_PROVIDER = "mock"  # mock | local | api
```

Change only this value, restart the kernel, and choose **Run All**. The three
approaches share the same notebook workflow but have different requirements:

| Provider | Additional requirements | Network use | Typical purpose |
|---|---|---|---|
| `mock` | None | None | Fast, reproducible learning and framework comparison |
| `local` | llama.cpp package and the Qwen GGUF download | Download only; inference is offline | Real model inference on the user's laptop |
| `api` | Gemini API key, account, internet access and available quota | Each model call uses Gemini | Hosted-model experimentation |

### Mock: simplest and default

Leave `MODEL_PROVIDER = "mock"` and run the notebook. Mock requires no API key,
model download or model-serving process. It is deterministic, runs on CPU and
is the mode used by the automated tests. The framework packages are still
needed for the corresponding LangGraph, CrewAI or OpenAI Agents notebook.

### Local: Qwen on the laptop

Local inference is not installed or downloaded automatically. The model file is
about 640 MB and is excluded from Git. Install the notebook environment with
the additional llama.cpp package:

```bash
uv sync --group notebooks \
  --extra langgraph \
  --extra crewai \
  --extra openai-agents \
  --extra local-llama-cpp \
  --frozen
uv run --no-sync python -m ipykernel install --user \
  --name agentic-ai-tutorial \
  --display-name "Python 3.11 (agentic-ai-tutorial)"
```

Some platforms may need a C/C++ build toolchain if a compatible
`llama-cpp-python` wheel is unavailable. Download the recorded Qwen model to the
path expected by every case-study notebook, then verify it:

```bash
curl -L --fail \
  --output models/local/Qwen3-0.6B-Q8_0.gguf \
  https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/1eaf4d9/Qwen3-0.6B-Q8_0.gguf
shasum -a 256 models/local/Qwen3-0.6B-Q8_0.gguf
```

Expected SHA-256:
`9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`.
Launch Jupyter without changing the installed extras:

```bash
uv run --no-sync jupyter lab notebooks
```

Set `MODEL_PROVIDER = "local"`, restart the kernel and run all cells. The
notebook creates Qwen when the workflow runs; no separate model server or
terminal process is required. Restarting or shutting down the kernel guarantees
that its memory is released. See the [local model guide](models/local/README.md)
for provenance and optional qualification tests.

### API: Gemini

Gemini uses `gemini-3.1-flash-lite` by default. It requires a Gemini API key,
internet access and sufficient provider quota; availability, limits and charges
are controlled by Google. Set `MODEL_PROVIDER = "api"`, restart the kernel and
run all cells. If `GEMINI_API_KEY` is not already available, the notebook asks
for the key through a hidden input prompt, so no terminal command is required.

With `SAVE_API_CREDENTIAL = True`, the key is reused from
`.private/gemini_api_key`. This ignored file has user-only permissions but is
local plaintext storage; set the option to `False` on a shared computer and
shut down the kernel when finished. The notebooks never print the key.

For non-notebook development, the framework extras can also be installed
individually:

```bash
uv sync --dev --extra langgraph --frozen
uv sync --dev --extra crewai --frozen
uv sync --dev --extra openai-agents --frozen
```

## Notebook map

| Tutorial material | Plain Python | LangGraph | CrewAI | OpenAI Agents |
|---|---|---|---|---|
| Seven patterns | [notebook](notebooks/patterns/plain_python_patterns.ipynb) | [notebook](notebooks/patterns/langgraph_patterns.ipynb) | [notebook](notebooks/patterns/crewai_patterns.ipynb) | [notebook](notebooks/patterns/openai_agents_patterns.ipynb) |
| Research assistant | [notebook](notebooks/case_studies/research_assistant/plain_python.ipynb) | [notebook](notebooks/case_studies/research_assistant/langgraph.ipynb) | [notebook](notebooks/case_studies/research_assistant/crewai.ipynb) | [notebook](notebooks/case_studies/research_assistant/openai_agents.ipynb) |
| Data-analysis assistant | [notebook](notebooks/case_studies/data_analysis_assistant/plain_python.ipynb) | [notebook](notebooks/case_studies/data_analysis_assistant/langgraph.ipynb) | [notebook](notebooks/case_studies/data_analysis_assistant/crewai.ipynb) | [notebook](notebooks/case_studies/data_analysis_assistant/openai_agents.ipynb) |
| Simulated service assistant | [notebook](notebooks/case_studies/service_assistant/plain_python.ipynb) | [notebook](notebooks/case_studies/service_assistant/langgraph.ipynb) | [notebook](notebooks/case_studies/service_assistant/crewai.ipynb) | [notebook](notebooks/case_studies/service_assistant/openai_agents.ipynb) |

Every notebook contains its own Open in Colab badge. The
[notebook guide](notebooks/README.md) describes the matched learning path.
Case studies that use only the most appropriate framework are discoverable in
the extensible [independent case-study catalogue](notebooks/case_studies/independent/);
new cases are added there without changing this framework-comparison table.

### Colab links

- Patterns: [plain Python](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/patterns/plain_python_patterns.ipynb), [LangGraph](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/patterns/langgraph_patterns.ipynb), [CrewAI](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/patterns/crewai_patterns.ipynb), [OpenAI Agents](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/patterns/openai_agents_patterns.ipynb).
- Research assistant: [plain Python](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/case_studies/research_assistant/plain_python.ipynb), [LangGraph](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/case_studies/research_assistant/langgraph.ipynb), [CrewAI](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/case_studies/research_assistant/crewai.ipynb), [OpenAI Agents](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/case_studies/research_assistant/openai_agents.ipynb).
- Data analysis: [plain Python](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/case_studies/data_analysis_assistant/plain_python.ipynb), [LangGraph](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/case_studies/data_analysis_assistant/langgraph.ipynb), [CrewAI](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/case_studies/data_analysis_assistant/crewai.ipynb), [OpenAI Agents](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/case_studies/data_analysis_assistant/openai_agents.ipynb).
- Simulated service: [plain Python](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/case_studies/service_assistant/plain_python.ipynb), [LangGraph](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/case_studies/service_assistant/langgraph.ipynb), [CrewAI](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/case_studies/service_assistant/crewai.ipynb), [OpenAI Agents](https://colab.research.google.com/github/jmdvinodjmd/agentic-ai-tutorial/blob/main/notebooks/case_studies/service_assistant/openai_agents.ipynb).
- Independent cases: browse the [case-study catalogue](notebooks/case_studies/independent/); each case README provides its current Colab link.

## Paper-to-notebook map

- Agent components and seven orchestration patterns → the four pattern notebooks.
- Evidence-grounded research and claim-evidence ledgers → research-assistant row.
- Tool-mediated deterministic computation → data-analysis row.
- Permissions, approvals, effects and recovery → simulated-service row.
- Evaluation, traces, budgets and stopping → final evaluation section of every notebook.
- Prompt injection, provenance, unsafe code and least privilege → case-specific safety checks.

## Reproducibility and testing

Inputs and scripted decisions are versioned under `data/`; schemas, provider
adapters, tools, canonical traces, metrics and safety primitives live under
`src/agentic_tutorial/`. Full orchestration does not. Mock notebooks are executed
twice and compared for equality.

```bash
make check
make setup-all                 # optional: install all framework/local extras
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest -q tests/test_notebook_mock_execution.py
```

CI runs core/plain notebooks without credentials and each framework in a clean,
separate optional-dependency job. Gemini and real local-model qualification are
optional integration checks and are not required in CI.

After exporting `GEMINI_API_KEY`, run Gemini's opt-in 8/8 qualification with:

```bash
uv run pytest -q tests/test_optional_gemini_qualification.py
```

The local-Qwen download, checksum and qualification commands are in the
[local model guide](models/local/README.md). Both live checks use explicit fault
injection for the malformed-response recovery probe; neither stores credentials
or downloads model weights.

## Limitations

- Fixtures and datasets are deliberately small and cannot establish external or causal validity.
- Mock runs test orchestration and safeguards, not real-model semantic quality.
- CrewAI and OpenAI Agents carry more dependency/runtime overhead than plain Python.
- The Qwen local candidate must pass the documented 8/8 qualification suite on the target laptop before it is advertised as selected.
- The service environment is simulated; it is not a durable transaction system.

## Licence

Apache License 2.0. See [LICENSE](LICENSE).

## Citation

If you use this tutorial in teaching, research or other work, please cite:

```bibtex
@misc{chauhan2026practical,
  author       = {Vinod Kumar Chauhan},
  title        = {A Practical Tutorial on Agentic AI},
  year         = {2026},
  howpublished = {GitHub repository},
  url          = {https://github.com/jmdvinodjmd/agentic-ai-tutorial}
}
```

## Disclaimer

This repository is provided solely for learning and explanatory purposes. Its
examples are simplified and may contain errors; they are not production-ready
systems or professional advice. Use, modify and run the material at your own
risk, and independently review it before applying it to real systems or data.
