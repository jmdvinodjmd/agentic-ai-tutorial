"""Validate and optionally execute the supplementary offline notebooks."""

from __future__ import annotations

import argparse
import ast
import asyncio
import inspect
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = (
    ROOT / "notebooks/01_components_walkthrough.ipynb",
    ROOT / "notebooks/02_execution_patterns.ipynb",
    ROOT / "notebooks/03_framework_comparison.ipynb",
)
MAX_NOTEBOOK_BYTES = 100_000
PROHIBITED = ("api_key=", "-----BEGIN PRIVATE KEY-----", "/Users/", "C:\\\\Users\\")
COPIED_IMPLEMENTATION_MARKERS = (
    "class LangGraphResearchAssistant",
    "class CrewAIResearchAssistant",
    "class OpenAIAgentsResearchAssistant",
)


def validate(path: Path) -> list[str]:
    """Return validation errors for one notebook."""
    errors: list[str] = []
    if not path.is_file():
        return [f"missing notebook: {path.relative_to(ROOT)}"]
    if path.stat().st_size > MAX_NOTEBOOK_BYTES:
        errors.append(f"{path.name}: larger than {MAX_NOTEBOOK_BYTES} bytes")
    try:
        notebook = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"{path.name}: cannot parse: {error}"]
    if notebook.get("nbformat") != 4 or not isinstance(notebook.get("cells"), list):
        errors.append(f"{path.name}: invalid notebook format")
        return errors
    source = "\n".join(
        "".join(cell.get("source", [])) for cell in notebook["cells"] if isinstance(cell, dict)
    )
    for marker in (*PROHIBITED, *COPIED_IMPLEMENTATION_MARKERS):
        if marker.lower() in source.lower():
            errors.append(f"{path.name}: prohibited content: {marker}")
    for cell in notebook["cells"]:
        if cell.get("cell_type") == "code" and (
            cell.get("execution_count") is not None or cell.get("outputs")
        ):
            errors.append(f"{path.name}: code outputs or execution counts are not cleared")
    return errors


def execute(path: Path) -> None:
    """Execute code cells in one shared namespace without a notebook server."""
    notebook = json.loads(path.read_text(encoding="utf-8"))
    namespace: dict[str, object] = {"__name__": "__notebook__"}
    old_mode = os.environ.get("AGENTIC_TUTORIAL_MODE")
    os.environ["AGENTIC_TUTORIAL_MODE"] = "mock"
    try:
        for index, cell in enumerate(notebook["cells"], start=1):
            if cell.get("cell_type") != "code":
                continue
            source = "".join(cell.get("source", []))
            code = compile(
                source,
                f"{path.name}:cell-{index}",
                "exec",
                flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
            )
            result = eval(code, namespace)
            if inspect.isawaitable(result):
                asyncio.run(result)
    finally:
        if old_mode is None:
            os.environ.pop("AGENTIC_TUTORIAL_MODE", None)
        else:
            os.environ["AGENTIC_TUTORIAL_MODE"] = old_mode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    errors = [error for path in NOTEBOOKS for error in validate(path)]
    if errors:
        print("Notebook checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    if args.execute:
        for path in NOTEBOOKS:
            execute(path)
    action = "validated and executed" if args.execute else "validated"
    print(f"Notebook checks passed: {len(NOTEBOOKS)} notebooks {action} offline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
