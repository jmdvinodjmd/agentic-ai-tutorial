# Reproducibility

The deterministic baseline is defined by versioned case-study fixtures, canonical schema and policy versions, the task-specification hash, provider metadata and `uv.lock`. Run manifests record the material configuration; JSONL traces record canonical operations. The matched comparison commits a small configuration, result and CSV summary.

Check the committed artefacts without a model, credentials, network access or external service:

```bash
uv run python scripts/check_reproducibility.py
```

The checker validates the task and comparison configuration hashes, fixture manifest and trace schemas, trace ordering, dependency lock, and the optional local-model checksum metadata. The model file itself is downloaded separately and verified as described in [the local-model guide](local_model.md).

Timestamps, run identifiers, durations, latency, memory and local paths are operational observations. They are normalised or excluded from deterministic equality. Task outcomes, schema validity, evidence scores, action counts and canonical trajectories are the deterministic comparison fields.

Generated runs stay beneath ignored `outputs/` paths. Only deliberately small, documented fixtures and comparison snapshots belong in version control.
