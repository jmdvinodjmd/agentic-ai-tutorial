"""Strict loading for small, versioned JSON teaching fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError


def load_fixture(path: str | Path, schema: type[BaseModel]) -> BaseModel:
    """Load one JSON fixture and validate it against the supplied contract."""

    fixture_path = Path(path)
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        return schema.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        raise ValueError(f"invalid fixture: {fixture_path}") from error


__all__ = ["load_fixture"]
