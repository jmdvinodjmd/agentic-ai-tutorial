# Shared foundation design decisions

This document explains the design decisions behind the reusable, framework-independent foundation.

## Canonical schemas

- Schema version `1` is included on every independently serialisable canonical model. Version migration is deliberately deferred until a second version exists.
- Canonical models are immutable and reject unknown fields so provider or framework objects cannot leak into shared state silently.
- Actions use a discriminated union containing only tool and finish actions. Planning, approval and routing actions belong to later tickets.
- Usage contains cumulative token and call counts. Unavailable or partially available token fields are represented explicitly as `null`, never zero. Agent state requires consecutive step numbers, monotonic known usage, and equality between state usage and the last step.
- Default budgets are finite and conservative; enforcement is provided by the shared budget manager.
- A committed complete-run trajectory fixture provides stable schema evidence alongside canonical event traces.

## Provider-independent model interface

- `ModelClient` is an async-first structural protocol. Implementations expose stable provider/model identifiers and capability metadata, and return only canonical `ModelResponse` values.
- The common generation settings intentionally cover only temperature, output limit, seed and a streaming request flag. Provider-specific options remain inside adapter construction.
- Typed `ModelConfig` selects providers through a registry. Tutorials therefore need no provider imports or credential handling.
- Capability validation occurs before adapter invocation and raises `UnsupportedCapabilityError` rather than silently degrading a request.
- Provider adapters map SDK exceptions into a small shared hierarchy. Those errors can be converted into sanitised canonical `AgentError` records without retaining vendor objects.

## Deterministic mock and replay

- `DeterministicMockClient` consumes a finite, versioned scenario in step order. It deliberately does not simulate linguistic variation or silently loop a final response.
- `ReplayClient` requires a provenance header followed by canonical request-response pairs in JSONL. It compares messages, complete tool definitions, an explicit stable response-schema identifier and common generation settings before returning a response.
- Both clients validate tool-call names and structured outputs against the current request. Exhaustion, malformed fixtures and divergence use explicit shared model errors.
- Offline fixtures carry canonical provider/model identity. Configuration must match that identity, preventing a run manifest from labelling fixture output as a different model.
- Determinism is assessed using byte-equivalent canonical response sequences. Response and trajectory fixtures contain no generated timestamps.

## Shared tools

- Typed functions are registered once and exposed through canonical `ToolDefinition` values; Pydantic models derived from signatures reject missing, extra and mistyped arguments before invocation.
- The executor accepts only canonical `ToolCall` values and returns `ToolResult` for success, denial, validation failure, timeout and sanitised exceptions.
- Per-run allowlists provide least privilege. Canonically side-effecting tools additionally require a token matching both tool name and call identifier; tutorial built-ins are read-only.
- Synchronous functions run in worker threads so the async executor can enforce timeouts without blocking its event loop. Timed-out threads cannot be force-killed, so side-effecting synchronous handlers must remain disallowed without approval and should be designed cooperatively.

## Minimal plain-Python loop

- The reference loop asks `ModelClient` for a stable `AgentDecision` envelope containing only canonical tool or finish actions.
- A finite `for` loop delegates model-call, step, elapsed-time, token and repeated-action limits to the sole shared `BudgetManager`.
- Malformed structured decisions create failed steps with no fabricated action. Tool failures remain canonical observations and are available to a later model decision.
- Execution evidence is represented by canonical `AgentState` trajectories and trace events.

## Checkpoint persistence

- `CheckpointStore` is async so execution code is storage-neutral. JSON uses same-directory temporary files, flush/fsync and atomic replacement; SQLite uses a transactional upsert.
- Checkpoints contain the complete canonical state, including task, messages, steps, usage, original budget, termination and final answer. They never contain model clients, credentials or framework objects.
- Only explicitly interrupted states may resume. Resumption clears that interruption marker and continues step numbering and cumulative usage from the restored state.

## Budgets and circuit breakers

- `BudgetManager` is the sole execution-limit authority.
- Canonical `Usage` now preserves elapsed time, failures and optional monetary cost alongside calls and partially available token counts, so remaining resources survive checkpoints.
- Checks cover steps, model/tool calls, known tokens, elapsed time, failures, optional known cost, identical actions and two-action short cycles. Unknown tokens or cost never disable other limits.
- Nested managers must fit within the parent manager's currently remaining calls, steps, tool calls and failure allowance.

## Tracing and manifests

- Append-only JSONL events use one shared enum, run identifier and consecutive sequence, while payloads contain operational decisions rather than private reasoning.
- The plain-Python loop emits run start, model request/response, decision, tool request/result, state transition, budget, checkpoint, error and termination events. `human_decision` is defined now for later approval workflows.
- Sanitisation recursively redacts configured keys and literal secret values before serialisation. Trace payloads never retain exception objects or credentials.
- Manifests record schema/code/Python/dependency/provider/model/environment identity. `configuration_hash` is SHA-256 over canonical JSON (`sort_keys=True`, compact separators), making equivalent typed configurations hash identically.
- Deterministic comparisons normalise run identifiers, timestamps and duration fields while preserving event order and structured outcomes.
