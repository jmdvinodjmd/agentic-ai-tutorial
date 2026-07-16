"""Release-checker regression tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_notebooks_parse_and_execute_offline() -> None:
    result = _run("check_notebooks.py", "--execute")
    assert result.returncode == 0, result.stdout + result.stderr


def test_reproducibility_artefacts_are_consistent() -> None:
    result = _run("check_reproducibility.py")
    assert result.returncode == 0, result.stdout + result.stderr


def test_public_content_passes_release_audit() -> None:
    result = _run("audit_public.py")
    assert result.returncode == 0, result.stdout + result.stderr
