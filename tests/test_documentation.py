"""Public documentation consistency checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_documentation_structure_links_and_commands() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_docs.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
