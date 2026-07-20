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
PATTERN_NOTEBOOKS = (
    (ROOT / "notebooks" / "patterns" / "plain_python_patterns.ipynb", None),
    (ROOT / "notebooks" / "patterns" / "langgraph_patterns.ipynb", "langgraph"),
)


async def _await_result(result: Awaitable[Any]) -> Any:
    return await result


@pytest.mark.parametrize(("notebook_path", "required_module"), PATTERN_NOTEBOOKS)
def test_pattern_notebook_executes_top_to_bottom(
    monkeypatch: pytest.MonkeyPatch,
    notebook_path: Path,
    required_module: str | None,
) -> None:
    if required_module is not None:
        pytest.importorskip(required_module)
    monkeypatch.chdir(ROOT)
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    namespace: dict[str, object] = {"__name__": "__notebook__"}

    for index, cell in enumerate(notebook["cells"], start=1):
        if cell.get("cell_type") != "code":
            continue
        assert cell.get("execution_count") is None
        assert not cell.get("outputs")
        source = "".join(cell.get("source", []))
        code = compile(
            source,
            f"{notebook_path.name}:cell-{index}",
            "exec",
            flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
        )
        result = eval(code, namespace)
        if inspect.isawaitable(result):
            asyncio.run(_await_result(result))

    evaluations = namespace["pattern_evaluations"]
    assert isinstance(evaluations, dict)
    assert set(evaluations) == {
        "prompt_chaining",
        "routing",
        "parallelisation",
        "react",
        "planner_executor",
        "critic_reviser",
        "orchestrator_worker",
    }
    assert all(evaluations.values())
