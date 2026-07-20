"""Execute the milestone notebook with its deterministic mock backend."""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
from collections.abc import Awaitable
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[1]
NOTEBOOK = ROOT / "notebooks" / "patterns" / "plain_python_patterns.ipynb"


async def _await_result(result: Awaitable[Any]) -> Any:
    return await result


def test_plain_python_pattern_notebook_executes_top_to_bottom(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(ROOT)
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    namespace: dict[str, object] = {"__name__": "__notebook__"}

    for index, cell in enumerate(notebook["cells"], start=1):
        if cell.get("cell_type") != "code":
            continue
        assert cell.get("execution_count") is None
        assert not cell.get("outputs")
        source = "".join(cell.get("source", []))
        code = compile(
            source,
            f"{NOTEBOOK.name}:cell-{index}",
            "exec",
            flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
        )
        result = eval(code, namespace)
        if inspect.isawaitable(result):
            asyncio.run(_await_result(result))

    state = namespace["state"]
    evaluation = namespace["evaluation"]
    assert isinstance(state, dict) and state["termination"] == "criteria_met"
    assert isinstance(evaluation, dict) and all(evaluation.values())
