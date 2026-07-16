"""Run the shared research-assistant task with CrewAI Flow orchestration."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from agentic_tutorial.case_study import CaseStudyModelFactory, CaseStudyVariant
from agentic_tutorial.models import ModelConfig, create_model_client
from agentic_tutorial.models.providers import ReplayClient
from agentic_tutorial.schemas import Budget
from frameworks.crewai import CrewAICaseStudy


def _model_factory(args: argparse.Namespace) -> CaseStudyModelFactory | None:
    if args.mode == "mock":
        return None
    if args.mode == "replay":
        if not args.replay_fixture:
            raise SystemExit("--replay-fixture is required in replay mode")
        return lambda _variant, _offset: ReplayClient.from_jsonl(args.replay_fixture)
    model_path = args.model_path or os.getenv("AGENTIC_TUTORIAL_LOCAL_MODEL_PATH")
    if not model_path:
        raise SystemExit("configure --model-path or AGENTIC_TUTORIAL_LOCAL_MODEL_PATH")
    configuration = ModelConfig.model_validate(
        {
            "provider": "local-llama-cpp",
            "model": Path(model_path).stem,
            "execution_mode": "local",
            "settings": {"temperature": 0.0, "max_output_tokens": 1024, "seed": 0},
            "options": {
                "model_path": model_path,
                "metadata_path": args.model_metadata,
                "context_size": 4096,
                "thread_count": max(1, os.cpu_count() or 1),
            },
        }
    )
    return lambda _variant, _offset: create_model_client(configuration)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=tuple(CaseStudyVariant), default="standard")
    parser.add_argument("--run-id")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--interrupt-after-steps", type=int)
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--mode", choices=("mock", "replay", "local"), default="mock")
    parser.add_argument("--replay-fixture")
    parser.add_argument("--model-path")
    parser.add_argument("--model-metadata", default="models/local/model_metadata.json")
    args = parser.parse_args()
    variant = CaseStudyVariant(args.variant)
    run_id = args.run_id or f"crewai-{variant.value}"
    budget = Budget(max_steps=args.max_steps) if args.max_steps is not None else None
    state = asyncio.run(
        CrewAICaseStudy(model_factory=_model_factory(args)).run(
            variant,
            run_id=run_id,
            resume=args.resume,
            interrupt_after_steps=args.interrupt_after_steps,
            budget=budget,
        )
    )
    print(
        json.dumps(
            {
                "final_answer": state.final_answer.model_dump(mode="json")
                if state.final_answer
                else None,
                "run_id": state.run_id,
                "termination": state.termination.model_dump(mode="json")
                if state.termination
                else None,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
