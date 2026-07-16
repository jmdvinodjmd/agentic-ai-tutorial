"""Run manifests recording environment, configuration and dependency identity."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from agentic_tutorial.schemas import SCHEMA_VERSION


class RunManifest(BaseModel):
    """Reproducibility metadata stored alongside a trace."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    manifest_version: Literal["1"] = "1"
    run_id: str = Field(min_length=1)
    created_at: datetime
    code_version: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION
    python_version: str
    dependencies: dict[str, str]
    provider: str
    model: str
    configuration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_specification_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    environment: dict[str, JsonValue]


def build_run_manifest(
    *,
    run_id: str,
    code_version: str,
    provider: str,
    model: str,
    configuration: BaseModel | dict[str, JsonValue],
    task_specification_hash: str | None = None,
    created_at: datetime | None = None,
    dependencies: tuple[str, ...] = ("agentic-ai-tutorial", "pydantic"),
) -> RunManifest:
    """Build a manifest with a canonical SHA-256 configuration hash."""
    configuration_data = (
        configuration.model_dump(mode="json")
        if isinstance(configuration, BaseModel)
        else configuration
    )
    encoded = json.dumps(configuration_data, sort_keys=True, separators=(",", ":")).encode()
    versions: dict[str, str] = {}
    for dependency in dependencies:
        try:
            versions[dependency] = importlib.metadata.version(dependency)
        except importlib.metadata.PackageNotFoundError:
            versions[dependency] = "unavailable"
    return RunManifest(
        run_id=run_id,
        created_at=created_at or datetime.now(UTC),
        code_version=code_version,
        python_version=platform.python_version(),
        dependencies=versions,
        provider=provider,
        model=model,
        configuration_hash=hashlib.sha256(encoded).hexdigest(),
        task_specification_hash=task_specification_hash,
        environment={
            "implementation": platform.python_implementation(),
            "operating_system": platform.system(),
            "machine": platform.machine(),
            "executable_prefix": sys.prefix,
        },
    )


def write_manifest(path: str | Path, manifest: RunManifest) -> None:
    """Write a deterministic JSON representation to the predictable run directory."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
