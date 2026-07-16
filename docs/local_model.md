# Optional local model

The `local-llama-cpp` provider demonstrates real, CPU-first inference without a cloud API. Deterministic mock and replay remain the default for tutorials, tests and reproducible comparisons. The provider fails explicitly if its optional runtime, model file or requested capability is unavailable.

## Runtime installation

The adapter uses the maintained [`llama-cpp-python`](https://github.com/abetlen/llama-cpp-python) integration and imports it only when this provider is constructed:

```bash
uv sync --dev --extra local-llama-cpp
```

Core installation does not install llama.cpp. Platform-specific compiler and acceleration options are documented by the runtime project. The repository configuration uses CPU execution (`n_gpu_layers=0`) by default.

## Example model

The recorded example is [`Qwen/Qwen3-0.6B-GGUF`](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF), file `Qwen3-0.6B-Q8_0.gguf`, quantisation `Q8_0`, licensed Apache-2.0. Download weights separately; they are never installed or committed by this project.

```bash
curl -L "https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q8_0.gguf?download=true" \
  -o models/local/Qwen3-0.6B-Q8_0.gguf
```

Verify the pinned SHA-256 checksum before use:

```bash
printf '%s  %s\n' \
  '9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031' \
  'models/local/Qwen3-0.6B-Q8_0.gguf' | shasum -a 256 -c -
```

On systems with GNU coreutils, replace `shasum -a 256` with `sha256sum`. Machine-readable provenance is in [`models/local/model_metadata.json`](../models/local/model_metadata.json). If a different model is used, copy and update the metadata and configuration files, including the exact repository, revision, filename, checksum and licence.

## Configuration and offline execution

Set the model path after download:

```bash
export AGENTIC_TUTORIAL_LOCAL_MODEL_PATH=models/local/Qwen3-0.6B-Q8_0.gguf
uv run --extra local-llama-cpp python evaluation/local_model.py
```

[`docs/local_model.example.json`](local_model.example.json) shows context size, output length, CPU thread count, temperature, seed, timeout and capability flags. The provider validates the recorded checksum. Once the runtime and model are installed, execution performs no network request.

The dependency-free adapter smoke check is:

```bash
uv run agentic-tutorial local-fake-smoke
```

The optional evaluation runs one structured invocation and a small case-study subset. It reports structured-output validity, task completion, tool-selection success, latency, token usage when supplied by the runtime and peak process memory when the operating system exposes it. These measurements are unavailable rather than zero when they cannot be observed.

## Limitations

Sub-1B models are mainly useful here to demonstrate real local inference. They may fail structured output, tool selection, multi-step planning, critique or multi-agent work. Native JSON and tool calling depend on the selected model/chat format and runtime; disable the corresponding capability flag when unsupported. Local RSS is a process-level peak, not model-only memory, and is not available on every operating system.
