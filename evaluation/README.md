# Deterministic evaluation

The common evaluator scores canonical state and traces rather than relying on an LLM judge. Any implementation can be compared by returning the same `AgentState` for the centrally versioned case-study variants.

## Metric definitions

- **Task completion:** termination matches the annotated outcome, including interruption for clarification.
- **Final-answer validity:** the canonical final-answer schema validates; clarification runs are valid without an answer.
- **Evidence precision and recall:** selected source identifiers are compared with the annotated expected set.
- **Provenance validity:** evidence identifiers are unique and present in the common ground truth.
- **Unsupported-claim rate:** the fraction of evidence claims attached to unknown sources.
- **Tool-selection validity:** the fraction of tool actions permitted by the common policy.
- **Routing correctness:** all selected tools belong to the annotated flow for that task variant.
- **Trajectory validity:** trace sequences are consecutive and include explicit termination.
- **Unnecessary and repeated actions:** actions outside the expected flow and repeated logical tool name/argument pairs.
- **Recovery:** a run with recorded failures subsequently reaches its expected outcome.
- **Budget adherence:** calls, steps, tokens, failures, elapsed time and cost remain within the canonical budget.
- **Human intervention:** count of canonical human-decision events.
- **Resources:** model/tool calls, tokens, latency, cost and peak memory. Unreported values are `null`, never zero.

Metrics are deterministic and intentionally narrow. Semantic answer quality beyond the explicit annotations is not inferred, and prompt-injection safety cannot be established from final-answer scoring alone.

Repeated deterministic runs must match on outcomes and trajectory metrics. Wall-clock latency is retained as an observed measurement and is excluded from byte-equivalence claims because operating-system scheduling varies.

The four-way [matched framework comparison](comparison/README.md) applies these unchanged metrics to the standard task and adds explicitly observational implementation measurements.
