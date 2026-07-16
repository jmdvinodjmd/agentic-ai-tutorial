"""Command-line entry point for repository-level developer checks."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    """Build the repository command-line parser."""
    parser = argparse.ArgumentParser(
        prog="agentic-tutorial",
        description="Run Agentic AI Tutorial repository commands.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "smoke",
        help="Run the deterministic offline repository smoke check.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a selected repository command."""
    args = build_parser().parse_args(argv)
    if args.command == "smoke":
        print(json.dumps({"mode": "offline", "status": "ok"}, sort_keys=True))
        return 0
    return 2
