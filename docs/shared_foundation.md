# Shared foundation design decisions

This document records decisions made while implementing Tickets T01–T03. It does not define orchestration, live-provider behaviour or canonical tracing.

## T01: canonical schemas

- Schema version `1` is included on every independently serialisable canonical model. Version migration is deliberately deferred until a second version exists.
- Canonical models are immutable and reject unknown fields so provider or framework objects cannot leak into shared state silently.
- Actions use a discriminated union containing only tool and finish actions. Planning, approval and routing actions belong to later tickets.
- Usage contains cumulative token and call counts. Agent state requires consecutive step numbers, monotonic cumulative usage, and equality between state usage and the last step.
- Default budgets are finite and conservative. T08 will provide enforcement; T01 defines only the contract.
- The committed complete-run evidence is a canonical trajectory fixture, not a trace. Canonical event tracing remains deferred to T09.

## T02: provider-independent model interface

- `ModelClient` is an async-first structural protocol. Implementations expose stable provider/model identifiers and capability metadata, and return only canonical `ModelResponse` values.
- The common generation settings intentionally cover only temperature, output limit, seed and a streaming request flag. Provider-specific options remain inside adapter construction.
- Typed `ModelConfig` selects providers through a registry. Tutorials therefore need no provider imports or credential handling.
- Capability validation occurs before adapter invocation and raises `UnsupportedCapabilityError` rather than silently degrading a request.
- Provider adapters map SDK exceptions into a small shared hierarchy. Those errors can be converted into sanitised canonical `AgentError` records without retaining vendor objects.

## T03: deterministic mock and replay

- `DeterministicMockClient` consumes a finite, versioned scenario in step order. It deliberately does not simulate linguistic variation or silently loop a final response.
- `ReplayClient` requires a provenance header followed by canonical request-response pairs in JSONL. It compares messages, complete tool definitions, response-schema identity and common generation settings before returning a response.
- Both clients validate tool-call names and structured outputs against the current request. Exhaustion, malformed fixtures and divergence use explicit shared model errors.
- Offline fixtures carry canonical provider/model identity. Configuration must match that identity, preventing a run manifest from labelling fixture output as a different model.
- Determinism is assessed using byte-equivalent canonical response sequences. Timestamps are absent because these are response/trajectory fixtures, not T09 trace events.
