"""Run the common case study through the framework-independent baseline."""

from __future__ import annotations

import argparse
import json

from agentic_tutorial.case_study import CaseStudyVariant
from agentic_tutorial.case_study.plain_python import run_case_study
from agentic_tutorial.schemas import Budget


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=tuple(CaseStudyVariant), default="standard")
    parser.add_argument("--run-id")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--interrupt-after-steps", type=int)
    parser.add_argument("--max-steps", type=int)
    args = parser.parse_args()
    variant = CaseStudyVariant(args.variant)
    run_id = args.run_id or f"plain-python-{variant.value}"
    budget = Budget(max_steps=args.max_steps) if args.max_steps is not None else None
    state = run_case_study(
        variant,
        run_id=run_id,
        resume=args.resume,
        interrupt_after_steps=args.interrupt_after_steps,
        budget=budget,
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
