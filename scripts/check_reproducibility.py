"""Check committed reproducibility artefacts without external services."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agentic_tutorial.case_study import case_study_hash, load_definition
from agentic_tutorial.schemas import SCHEMA_VERSION
from agentic_tutorial.tracing import RunManifest, TraceEvent

ROOT = Path(__file__).resolve().parents[1]


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main() -> int:
    errors: list[str] = []
    definition = load_definition()
    comparison = _json(ROOT / "evaluation/comparison/results/result.json")
    if comparison.get("task_specification_hash") != case_study_hash(definition):
        errors.append("comparison task specification hash does not match the versioned task")
    if comparison.get("comparison_schema_version") != "1":
        errors.append("unexpected comparison schema version")
    if definition.safety.policy_version != "1":
        errors.append("unexpected case-study safety-policy version")
    if SCHEMA_VERSION != "1":
        errors.append("unexpected canonical schema version")
    config = _json(ROOT / "evaluation/comparison/results/config.json")
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    expected_hash = hashlib.sha256(canonical).hexdigest()
    if comparison.get("configuration_hash") != expected_hash:
        errors.append("comparison configuration hash is inconsistent")
    manifest_path = ROOT / "tests/fixtures/tracing/example_manifest_v1.json"
    manifest = RunManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    if not manifest.schema_version or not manifest.configuration_hash:
        errors.append("example manifest lacks schema or configuration metadata")
    trace_path = ROOT / "tests/fixtures/tracing/example_trace_v1.jsonl"
    events = [
        TraceEvent.model_validate_json(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if [event.sequence for event in events] != list(range(1, len(events) + 1)):
        errors.append("example trace sequence is not contiguous")
    metadata = _json(ROOT / "models/local/model_metadata.json")
    checksum = metadata.get("sha256")
    if not isinstance(checksum, str) or len(checksum) != 64:
        errors.append("local-model metadata has no valid SHA-256 field")
    if not (ROOT / "uv.lock").is_file():
        errors.append("dependency lock is missing")
    if errors:
        print("Reproducibility checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "Reproducibility checks passed: fixtures, task/configuration hashes, policy/schema "
        "metadata, manifest, trace, lock and local-model checksum metadata."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
