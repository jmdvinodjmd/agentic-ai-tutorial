# Optional local model

Downloaded GGUF weights belong here but are ignored by Git. The committed
`model_metadata.json` records the Qwen3-0.6B GGUF filename, source revision,
licence and SHA-256 checksum. Set `AGENTIC_TUTORIAL_LOCAL_MODEL_PATH` to a
separately downloaded file; no notebook or test downloads weights automatically.

Official file: [Qwen/Qwen3-0.6B-GGUF — Q8_0](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/blob/main/Qwen3-0.6B-Q8_0.gguf)

```bash
curl -L --fail --output /absolute/path/Qwen3-0.6B-Q8_0.gguf \
  https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/1eaf4d9/Qwen3-0.6B-Q8_0.gguf
shasum -a 256 /absolute/path/Qwen3-0.6B-Q8_0.gguf
```

The expected SHA-256 is
`9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`.

The candidate remains unqualified until it passes all eight checks recorded in
`../qualification_candidates.json` on the target laptop CPU.

After downloading and checksum-verifying the recorded file, run the actual
selection gate from smallest candidate upward:

```bash
export AGENTIC_TUTORIAL_LOCAL_MODEL_PATH=/absolute/path/Qwen3-0.6B-Q8_0.gguf
uv sync --dev --extra local-llama-cpp --frozen
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest -q \
  tests/test_optional_local_qualification.py
```

An 8/8 report is required before changing `selection_status` from
`not_yet_qualified`; a failed candidate must remain recorded before adding the
next larger Qwen instruct candidate.
