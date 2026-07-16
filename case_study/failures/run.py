"""Run every deterministic controlled failure scenario."""

from __future__ import annotations

import asyncio
import json

from agentic_tutorial.failures import ScenarioRunner


def main() -> int:
    results = asyncio.run(ScenarioRunner().run_all())
    print(json.dumps([result.model_dump(mode="json") for result in results], sort_keys=True))
    return int(not all(result.passed for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
