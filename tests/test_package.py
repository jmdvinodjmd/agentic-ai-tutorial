"""Foundation smoke tests for the installable package and CLI."""

from __future__ import annotations

import json

import pytest

import agentic_tutorial
from agentic_tutorial.cli import main


def test_package_imports() -> None:
    assert agentic_tutorial.__version__ == "0.1.0"


def test_offline_smoke_is_deterministic(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["smoke"]) == 0
    first_output = _captured_stdout(capsys)

    assert main(["smoke"]) == 0
    second_output = _captured_stdout(capsys)

    assert first_output == second_output
    assert json.loads(first_output) == {"mode": "offline", "status": "ok"}


def _captured_stdout(capsys: pytest.CaptureFixture[str]) -> str:
    return capsys.readouterr().out.strip()
