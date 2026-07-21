"""Small, user-facing helpers for click-to-run tutorial notebooks."""

from __future__ import annotations

import os
from getpass import getpass
from pathlib import Path


def prepare_gemini_api_key(root: Path, *, save: bool = True) -> None:
    """Load a Gemini key or request it through Jupyter's hidden input widget.

    The optional on-disk copy lives below the repository's ignored ``.private``
    directory and is readable only by the current user.
    """
    variable = "GEMINI_API_KEY"
    credential_path = root / ".private/gemini_api_key"
    credential = os.getenv(variable, "")
    if not credential and credential_path.is_file():
        credential = credential_path.read_text(encoding="utf-8").strip()
    if not credential:
        credential = getpass(
            "Paste Gemini API key into the hidden input prompt, then press Enter: "
        ).strip()
    if not credential:
        raise RuntimeError(
            "No Gemini key was entered. Re-run this cell and use its hidden input prompt."
        )
    if save and not credential_path.is_file():
        credential_path.parent.mkdir(parents=True, exist_ok=True)
        credential_path.write_text(credential + "\n", encoding="utf-8")
        credential_path.chmod(0o600)
    os.environ[variable] = credential
