"""Command-line runner for deterministic tutorials and patterns."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from agentic_tutorial.education import PATTERN_NAMES, TUTORIAL_NAMES, run_pattern, run_tutorial
from agentic_tutorial.education.approval import run_approval_cli


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Agentic AI examples.")
    subparsers = parser.add_subparsers(dest="group", required=True)
    tutorials = subparsers.add_parser("tutorial")
    tutorials.add_argument("name", choices=TUTORIAL_NAMES)
    patterns = subparsers.add_parser("pattern")
    patterns.add_argument("name", choices=PATTERN_NAMES)
    approval = subparsers.add_parser("approval")
    approval.add_argument(
        "--decision", choices=("approve", "reject", "revise", "request_information")
    )
    approval.add_argument("--revised-title", default="Revised local submission")
    args = parser.parse_args(argv)
    if args.group == "tutorial":
        result = run_tutorial(args.name)
    elif args.group == "pattern":
        result = run_pattern(args.name)
    else:
        return run_approval_cli(args.decision, args.revised_title)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
