"""Audit tracked public files for release-blocking content and artefacts."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 1_000_000
BINARY_SUFFIXES = {".gguf", ".ggml", ".bin", ".safetensors", ".pt", ".onnx", ".dylib", ".so"}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?:api[_-]?key|secret|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}", re.I),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
)
ABSOLUTE_PATHS = (re.compile(r"/Users/[^\s)`]+"), re.compile(r"[A-Za-z]:\\\\Users\\\\"))


def tracked_files() -> list[Path]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True)
    tracked = [ROOT / item.decode() for item in result.stdout.split(b"\0") if item]
    untracked_result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    untracked = [ROOT / item.decode() for item in untracked_result.stdout.split(b"\0") if item]
    return sorted({*tracked, *untracked})


def main() -> int:
    errors: list[str] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT)
        if relative.parts and relative.parts[0] == ".private":
            errors.append(f"private development file is tracked: {relative}")
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            errors.append(f"prohibited model or binary artefact: {relative}")
        if path.stat().st_size > MAX_FILE_BYTES:
            errors.append(f"tracked file exceeds 1 MB: {relative}")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if relative in {Path("scripts/audit_public.py"), Path("scripts/check_notebooks.py")}:
            continue
        for pattern in (*SECRET_PATTERNS, *ABSOLUTE_PATHS):
            if pattern.search(text):
                errors.append(f"sensitive or machine-specific content: {relative}")
                break
        if path.suffix.lower() in {".md", ".ipynb"} and re.search(r"\bT(?:0\d|1\d|2[0-4])\b", text):
            errors.append(f"internal ticket identifier in public teaching content: {relative}")
    if errors:
        print("Public-content audit failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Public-content audit passed: {len(tracked_files())} tracked files checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
