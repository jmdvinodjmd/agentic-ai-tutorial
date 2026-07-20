"""Shared fixture loading tests."""

from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from agentic_tutorial.fixtures import load_fixture


class ExampleFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fixture_version: str
    value: int


def test_fixture_loader_validates_content(tmp_path: Path) -> None:
    path = tmp_path / "fixture.json"
    path.write_text('{"fixture_version":"1","value":3}', encoding="utf-8")

    assert load_fixture(path, ExampleFixture) == ExampleFixture(fixture_version="1", value=3)


def test_fixture_loader_rejects_malformed_or_schema_invalid_content(tmp_path: Path) -> None:
    path = tmp_path / "fixture.json"
    path.write_text('{"fixture_version":"1","value":"wrong"}', encoding="utf-8")

    with pytest.raises(ValueError, match="invalid fixture"):
        load_fixture(path, ExampleFixture)
