"""Check public teaching-page structure, local links and root-relative commands."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEACHING_PAGES = (
    tuple(sorted((ROOT / "tutorials").glob("*/README.md")))
    + tuple(sorted((ROOT / "patterns").glob("*/README.md")))
    + tuple(
        ROOT / path
        for path in (
            "case_study/plain_python/README.md",
            "case_study/langgraph/README.md",
            "case_study/crewai/README.md",
            "case_study/openai_agents/README.md",
        )
    )
)
REQUIRED_HEADINGS = (
    "## Purpose",
    "## Architecture",
    "## Run",
    "## Expected output",
    "## Concept introduced",
    "## Limitations",
    "## Next step",
)
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")


def public_markdown() -> tuple[Path, ...]:
    return tuple(
        path
        for path in ROOT.rglob("*.md")
        if not any(part in {".private", ".venv", ".pytest_cache"} for part in path.parts)
    )


def check_structure(errors: list[str]) -> None:
    for path in TEACHING_PAGES:
        text = path.read_text(encoding="utf-8")
        positions = [text.find(heading) for heading in REQUIRED_HEADINGS]
        missing = [
            heading
            for heading, position in zip(REQUIRED_HEADINGS, positions, strict=True)
            if position < 0
        ]
        if missing:
            errors.append(f"{path.relative_to(ROOT)}: missing {', '.join(missing)}")
        elif positions != sorted(positions):
            errors.append(f"{path.relative_to(ROOT)}: teaching headings are out of order")
        if "```mermaid" not in text and "```text" not in text:
            errors.append(f"{path.relative_to(ROOT)}: missing Mermaid or text architecture diagram")


def check_links(errors: list[str]) -> None:
    for path in public_markdown():
        text = path.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK.findall(text):
            clean = target.split("#", maxsplit=1)[0]
            if not clean or clean.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (path.parent / clean).resolve()
            if not resolved.exists():
                errors.append(f"{path.relative_to(ROOT)}: broken link {target!r}")


def check_commands(errors: list[str]) -> None:
    command_pattern = re.compile(r"^uv run python ([^\s]+)", re.MULTILINE)
    for path in public_markdown():
        text = path.read_text(encoding="utf-8")
        for command_target in command_pattern.findall(text):
            parts = shlex.split(command_target)
            if not parts or parts[0] == "-m" or parts[0].startswith("-"):
                continue
            target = ROOT / parts[0]
            if not target.is_file():
                errors.append(
                    f"{path.relative_to(ROOT)}: command target does not exist: {parts[0]}"
                )


def main() -> int:
    errors: list[str] = []
    check_structure(errors)
    check_links(errors)
    check_commands(errors)
    if errors:
        print("Documentation checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        f"Documentation checks passed: {len(TEACHING_PAGES)} teaching pages, "
        f"{len(public_markdown())} public Markdown files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
