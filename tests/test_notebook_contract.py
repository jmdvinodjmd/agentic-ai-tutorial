"""Static completeness checks for the notebook-first teaching surface."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
FRAMEWORKS = ("plain_python", "langgraph", "crewai", "openai_agents")
CASES = ("research_assistant", "data_analysis_assistant", "service_assistant")
EXPECTED_NOTEBOOKS = (
    ROOT / "notebooks/patterns/plain_python_patterns.ipynb",
    ROOT / "notebooks/patterns/langgraph_patterns.ipynb",
    ROOT / "notebooks/patterns/crewai_patterns.ipynb",
    ROOT / "notebooks/patterns/openai_agents_patterns.ipynb",
    *(
        ROOT / "notebooks/case_studies" / case / f"{framework}.ipynb"
        for case in CASES
        for framework in FRAMEWORKS
    ),
)


@pytest.mark.parametrize("notebook_path", EXPECTED_NOTEBOOKS)
def test_notebook_meets_delivery_contract(notebook_path: Path) -> None:
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    text = "".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    lowered = text.casefold()

    assert "open in colab" in lowered
    assert "pip" in lowered and "==" in text
    assert "git" in text and "clone" in text
    assert "main" in text
    assert "mock" in lowered
    assert "runtime" in lowered and "cpu" in lowered
    assert "trace" in lowered
    assert "evaluation" in lowered
    assert "limitation" in lowered
    assert "api_key =" not in lowered
    assert "gemini_api_key =" not in lowered

    for index, cell in enumerate(notebook["cells"], start=1):
        if cell.get("cell_type") != "code":
            continue
        assert cell.get("execution_count") is None
        assert cell.get("outputs") == []
        source = "".join(cell.get("source", []))
        compile(
            source, f"{notebook_path.name}:cell-{index}", "exec", ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
        )


def test_notebook_set_and_removed_legacy_roots_are_exact() -> None:
    actual = set((ROOT / "notebooks").glob("patterns/*.ipynb")) | set(
        (ROOT / "notebooks").glob("case_studies/*/*.ipynb")
    )
    assert actual == set(EXPECTED_NOTEBOOKS)
    for obsolete in (
        "case_study",
        "docs",
        "evaluation",
        "frameworks",
        "outputs",
        "patterns",
        "scripts",
        "tutorials",
    ):
        assert not (ROOT / obsolete).exists()
