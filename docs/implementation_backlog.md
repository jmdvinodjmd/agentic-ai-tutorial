**Implementation Backlog, Coding Standards and Reproducibility
Contract**

*Prepared as an executable specification for Codex and other coding
models*

| **Core principle: shared task, tools, schemas, safety and evaluation must remain independent of framework-specific orchestration. Every example must be minimal enough to teach one concept, yet reproducible enough to support scientific comparison.** |
|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|

# 1. Purpose and delivery strategy

The repository is both a teaching resource and a research artefact
supporting the proposed paper, A Practical Tutorial on Agentic AI.
Development should begin with the code because implementation will
expose conceptual ambiguities, determine which examples are genuinely
distinct, and generate the evidence, diagrams and code skeletons
required for the manuscript.

- The paper will show concise code skeletons; the repository will
  contain complete runnable examples.

- The research-assistant case study will be reused across plain Python
  and selected frameworks.

- Tutorial examples may be more numerous than the examples eventually
  included in the paper.

- Most automated tests must run without internet access or paid API
  credentials.

- Live provider runs are an optional validation layer, not a
  prerequisite for learning or testing.

# 2. Non-negotiable engineering contract

| **Rule**                          | **Required interpretation**                                                                                                                        |
|-----------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| **Conceptual isolation**          | Each tutorial introduces one primary concept. Supporting infrastructure may be reused, but unrelated capabilities must not be introduced silently. |
| **Fair comparison**               | Framework implementations must share the same task, prompts, tools, schemas, model settings, budgets, stopping rules and evaluation harness.       |
| **Provider independence**         | Core code must depend on a small internal model interface, not directly on a vendor SDK. Provider-specific code belongs only in adapters.          |
| **Offline-first reproducibility** | Every tutorial and integration test must have a deterministic mock or replay mode. A reader must be able to run the repository without an API key. |
| **Typed interfaces**              | Tasks, actions, tool calls, state transitions, errors, traces and final outputs must use typed schemas.                                            |
| **Bounded execution**             | Every loop must enforce iteration, time and model-call limits and detect repeated actions.                                                         |
| **Explicit failure semantics**    | Errors must be represented in state and classified as retryable, recoverable by fallback, human-escalated or terminal.                             |
| **Safe tools**                    | Tutorial tools should be read-only or simulated. Side-effecting tools require an explicit approval boundary.                                       |
| **Traceability**                  | Every run must produce a structured trace sufficient to reconstruct model calls, tool calls, state transitions, timing and termination.            |
| **Minimal duplication**           | Shared code must not be copied into framework folders. Framework folders should express orchestration only.                                        |
| **Versioned reproducibility**     | Python, framework and provider dependencies must be locked, and each experiment must record the versions actually used.                            |
| **No hidden success**             | Examples must expose expected outputs, known limitations and failure cases rather than showing only successful demonstrations.                     |

# 3. API independence and provider strategy

API lock-in is the principal architectural risk. The repository must
therefore distinguish the tutorial’s agentic concepts from the mechanics
of any particular model provider.

- Define a minimal ModelClient protocol exposing structured generation,
  optional tool-calling capability metadata, usage accounting and
  provider/model identity.

- Use a canonical internal Message, ToolDefinition, ToolCall,
  ModelResponse and Usage schema. Adapters translate between these
  schemas and vendor SDK objects.

- Provide at least three execution backends: DeterministicMockClient,
  ReplayClient and one live provider adapter. Additional providers can
  be added without modifying tutorials.

- Do not design the core interface around the richest vendor feature.
  Use the smallest common capability set needed by the tutorial.

- Where native tool calling differs substantially, normalise the result
  into the canonical ToolCall schema and document unavoidable semantic
  differences.

- Use environment variables only inside provider construction. No
  tutorial file should read API keys directly.

- Live tests must be opt-in and marked separately. They must skip
  cleanly when credentials are absent.

- Record provider, model identifier, model version where available,
  parameters and usage in each trace.

- Do not promise identical outputs across providers. Compare task and
  trajectory metrics, not textual identity.

# 4. Definition of done for every tutorial or framework example

1.  A short README states the learning objective and the concept
    deliberately excluded from the example.

2.  One command runs the example in deterministic mock or replay mode.

3.  One optional command runs it with a live provider through the shared
    adapter.

4.  Inputs and expected structured outputs are included.

5.  The example enforces budgets and stopping conditions.

6.  A structured trace is written to a predictable output path.

7.  Unit or integration tests verify the principal behaviour and at
    least one failure path.

8.  No provider-specific import appears outside provider adapters or
    explicitly provider-specific framework integration files.

9.  The example reuses shared tools and schemas rather than copying
    them.

10. The README identifies what differs from the preceding tutorial and
    links to the relevant paper section.

# 5. Ticket conventions

Tickets are intentionally detailed so they can be passed individually to
a coding model. A model should implement only the stated ticket,
preserve established public interfaces, run the specified tests, and
report any deviation explicitly. “Done” means all acceptance criteria
and reproducibility evidence are present, not merely that a
demonstration runs once.

# 6. Recommended implementation sequence

| **Phase**                               | **Tickets** | **Outcome**                                                                    |
|-----------------------------------------|-------------|--------------------------------------------------------------------------------|
| **Phase A: foundation**                 | T00-T05     | Repository, schemas, provider interface, deterministic clients and safe tools. |
| **Phase B: minimal agent and controls** | T06-T09     | Plain-Python loop, checkpointing, budgets and canonical tracing.               |
| **Phase C: educational examples**       | T10-T12     | Progressive components tutorial, human approval and key execution patterns.    |
| **Phase D: common case study**          | T13-T14     | Versioned research-assistant task and framework-free baseline.                 |
| **Phase E: framework implementations**  | T15-T18     | Matched implementations, with the fourth framework optional.                   |
| **Phase F: evaluation and safety**      | T19-T23     | Metrics, failure scenarios, policy controls and matched comparisons.           |
| **Phase G: release quality**            | T22,T24     | Documentation consistency, CI, compatibility and artefact release.             |

The first usable milestone is completion of Phase B. At that point, the
repository will already explain the mechanics of an agent and enforce
the central reproducibility contract. Framework work should not begin
before the common task, schemas, tools, tracing and budgets are stable.

# 7. Detailed implementation tickets

## T00 Bootstrap the repository and developer workflow

| **Epic**                     | Foundation                                        | **Priority**         | P0                     |
|------------------------------|---------------------------------------------------|----------------------|------------------------|
| **Depends on**               | None                                              | **Estimated scope**  | Medium                 |
| **Primary deliverable**      | Installable Python package with CI-ready commands | **Tutorial concept** | Repository consistency |
| **Required execution modes** | Offline only initially                            | **Paper relevance**  | All sections           |

**Objective.** Create the repository skeleton, packaging configuration
and standard developer commands that all subsequent tickets will use.

**Implementation scope.**

- Create the agreed src/, tutorials/, patterns/, frameworks/,
  case_study/, evaluation/, tests/, notebooks/ and docs/ directories.

- Configure pyproject.toml for Python 3.11 or later, package discovery,
  optional dependency groups and command-line entry points.

- Add formatter, linter and static type checker configuration.

- Add Makefile or task runner commands for setup, test, lint, typecheck
  and offline smoke tests.

- Create .env.example without real credentials and a root README with
  installation and execution modes.

- Add a dependency lock file using the selected environment manager.

**Non-goals and exclusions.**

- Do not implement agent logic or framework dependencies in this ticket.

**Acceptance criteria.**

- A clean clone installs successfully using the documented command.

- Importing agentic_tutorial succeeds.

- Offline smoke command completes without credentials.

- Lint and type-check commands are documented and pass.

- No empty placeholder module raises NotImplementedError during import.

**Required tests.**

- Packaging installation test.

- Import smoke test.

- CLI help smoke test.

**Reproducibility evidence.**

- Lock file committed.

- Tested Python version documented.

- CI command list recorded in README.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T01 Define canonical schemas and state contracts

| **Epic**                     | Shared core                                                                    | **Priority**         | P0                                       |
|------------------------------|--------------------------------------------------------------------------------|----------------------|------------------------------------------|
| **Depends on**               | T00                                                                            | **Estimated scope**  | Large                                    |
| **Primary deliverable**      | Pydantic schemas for task, messages, actions, tools, state, errors and outputs | **Tutorial concept** | Typed state and structured communication |
| **Required execution modes** | Offline                                                                        | **Paper relevance**  | Sections 3, 6 and 7                      |

**Objective.** Define the framework-independent data contracts used by
every tutorial, provider and framework implementation.

**Implementation scope.**

- Create schemas for TaskSpec, Message, ToolDefinition, ToolCall,
  ToolResult, ModelResponse, Usage, AgentStep, AgentState, AgentError,
  Budget, Termination and FinalAnswer.

- Use explicit enums or literals for action types, error classes and
  termination reasons.

- Provide serialisation to and from JSON.

- Include schema version metadata to support future migrations.

- Document invariants such as unique step numbers and monotonic usage
  totals.

**Non-goals and exclusions.**

- Do not implement memory databases or provider calls.

**Acceptance criteria.**

- All schemas validate representative valid examples and reject
  malformed examples.

- Schemas contain no provider or framework classes.

- State can be serialised and restored without information loss.

- Default values are conservative and do not enable unbounded execution.

**Required tests.**

- Positive and negative validation tests.

- JSON round-trip tests.

- Backward-compatible fixture test for schema version 1.

**Reproducibility evidence.**

- Committed JSON fixtures for a complete run.

- Schema version recorded in traces.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T02 Create the provider-independent model interface

| **Epic**                     | Provider abstraction                      | **Priority**         | P0                   |
|------------------------------|-------------------------------------------|----------------------|----------------------|
| **Depends on**               | T01                                       | **Estimated scope**  | Large                |
| **Primary deliverable**      | ModelClient protocol and capability model | **Tutorial concept** | Avoiding API lock-in |
| **Required execution modes** | Mock and live-capable                     | **Paper relevance**  | Sections 3 and 5     |

**Objective.** Create the narrow internal model interface through which
all tutorials request model decisions.

**Implementation scope.**

- Define an async-first ModelClient protocol with generate() accepting
  canonical messages, optional tools, response schema and generation
  settings.

- Define ModelCapabilities covering structured output, native tool
  calling, streaming and usage reporting.

- Return canonical ModelResponse objects only.

- Create a provider registry and construction function driven by
  configuration rather than direct imports in tutorials.

- Define standard exceptions for authentication, rate limits, timeouts,
  invalid responses and unsupported capabilities.

**Non-goals and exclusions.**

- Do not implement every vendor.

- Do not expose vendor message objects outside adapters.

**Acceptance criteria.**

- A mock implementation can satisfy the protocol without importing a
  vendor SDK.

- Tutorial code can switch provider through configuration only.

- Unsupported features fail with explicit capability errors.

- Provider exceptions are normalised into shared error types.

**Required tests.**

- Protocol conformance tests.

- Fake adapter tests for exception normalisation.

- Configuration-based provider selection tests.

**Reproducibility evidence.**

- Provider and model identity included in each response.

- Capability matrix fixture included.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T03 Implement deterministic mock and replay model clients

| **Epic**                     | Provider abstraction                     | **Priority**         | P0                                         |
|------------------------------|------------------------------------------|----------------------|--------------------------------------------|
| **Depends on**               | T02                                      | **Estimated scope**  | Large                                      |
| **Primary deliverable**      | DeterministicMockClient and ReplayClient | **Tutorial concept** | Offline reproducibility                    |
| **Required execution modes** | Offline                                  | **Paper relevance**  | All implementation and evaluation sections |

**Objective.** Allow every tutorial and automated test to run
deterministically without internet access or API credentials.

**Implementation scope.**

- Implement scripted responses keyed by scenario and step.

- Support deterministic structured responses and tool calls.

- Implement a replay client that reads recorded canonical responses from
  JSONL.

- Validate replay compatibility with the requested tools and response
  schema.

- Provide clear diagnostics when a replay trace and current request
  diverge.

**Non-goals and exclusions.**

- Do not mimic free-form natural variation; determinism is the
  objective.

**Acceptance criteria.**

- All tutorial tests can use one of these clients.

- Repeated runs with the same fixture produce byte-equivalent structured
  traces except timestamps.

- Replay mismatches fail clearly rather than silently substituting data.

**Required tests.**

- Determinism test across repeated runs.

- Replay mismatch tests.

- Malformed fixture tests.

**Reproducibility evidence.**

- Versioned scenario fixtures.

- Recorded fixture provenance documented.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T04 Add one reference live-provider adapter

| **Epic**                     | Provider abstraction                                          | **Priority**         | P1                              |
|------------------------------|---------------------------------------------------------------|----------------------|---------------------------------|
| **Depends on**               | T02,T03                                                       | **Estimated scope**  | Medium                          |
| **Primary deliverable**      | One fully tested live adapter selected at implementation time | **Tutorial concept** | Live validation without lock-in |
| **Required execution modes** | Offline test plus opt-in live                                 | **Paper relevance**  | Sections 3 and 5                |

**Objective.** Demonstrate that the internal interface supports a real
model while keeping live execution optional.

**Implementation scope.**

- Select one stable provider based on current official SDK support and
  document the rationale.

- Translate canonical messages, tool definitions and structured-output
  requests to the provider API.

- Normalise tool calls, usage and finish reasons.

- Read credentials only in provider construction.

- Implement retries only for classified transient errors and honour
  global budgets.

**Non-goals and exclusions.**

- Do not make the repository dependent on a paid API.

- Do not implement provider-specific advanced features unless required.

**Acceptance criteria.**

- All adapter unit tests use mocked SDK calls.

- Live smoke test is opt-in and skips when credentials are absent.

- No tutorial imports the provider SDK.

- Trace identifies provider, model and relevant parameters.

**Required tests.**

- Mocked SDK mapping tests.

- Authentication and rate-limit normalisation tests.

- Optional live smoke test.

**Reproducibility evidence.**

- One sanitised live trace stored or documented.

- SDK and model identifiers recorded.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T05 Build the shared tool registry and safe tool executor

| **Epic**                     | Shared core                                 | **Priority**         | P0                                     |
|------------------------------|---------------------------------------------|----------------------|----------------------------------------|
| **Depends on**               | T01                                         | **Estimated scope**  | Large                                  |
| **Primary deliverable**      | Typed tool registry, validator and executor | **Tutorial concept** | Tool use and environmental interaction |
| **Required execution modes** | Offline                                     | **Paper relevance**  | Sections 3, 4 and 7                    |

**Objective.** Provide one safe, framework-independent mechanism for
defining, validating and executing tools.

**Implementation scope.**

- Implement a decorator or registration API that derives schemas from
  typed Python functions.

- Validate tool names and arguments before execution.

- Return canonical ToolResult including status, timing, content and
  sanitised error information.

- Support sync and async tools.

- Implement allowlists and a side-effect classification.

- Provide read-only tutorial tools such as calculator, local search and
  deterministic paper catalogue search.

**Non-goals and exclusions.**

- No unrestricted shell execution.

- No real email, deletion or file mutation tools in core tutorials.

**Acceptance criteria.**

- Unknown tools and invalid arguments never execute.

- Errors are captured as ToolResult rather than uncaught exceptions.

- Framework implementations can wrap the same registered tools.

- Side-effecting tools require an approval token or remain simulated.

**Required tests.**

- Registry and schema-generation tests.

- Argument validation tests.

- Timeout and exception tests.

- Side-effect permission tests.

**Reproducibility evidence.**

- Tool version and arguments logged.

- Deterministic tool fixtures included.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T06 Implement the minimal plain-Python agent loop

| **Epic**                     | Core tutorial              | **Priority**         | P0                            |
|------------------------------|----------------------------|----------------------|-------------------------------|
| **Depends on**               | T02,T03,T05                | **Estimated scope**  | Large                         |
| **Primary deliverable**      | Minimal bounded agent loop | **Tutorial concept** | Sense-decide-act-observe loop |
| **Required execution modes** | Offline and optional live  | **Paper relevance**  | Sections 2 and 3              |

**Objective.** Expose the mechanics of an agent without relying on an
agent framework.

**Implementation scope.**

- Implement a loop that requests a canonical action, validates it,
  executes a tool or terminates, updates state and records a step.

- Support structured finish and tool actions.

- Enforce maximum model calls, iterations and elapsed time.

- Represent every failure in state.

- Provide one deterministic research-assistant task.

**Non-goals and exclusions.**

- Do not add planning, memory or multiple agents yet.

**Acceptance criteria.**

- The example completes in mock mode with a known final output.

- An invalid tool call is handled and recorded.

- The loop cannot run indefinitely.

- The implementation contains no framework-specific dependency.

**Required tests.**

- Successful trajectory test.

- Invalid action test.

- Maximum-iteration termination test.

- Repeated-action termination test.

**Reproducibility evidence.**

- Expected trace committed.

- README shows exact command and output schema.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T07 Add state persistence and checkpointing

| **Epic**                     | Core tutorial                             | **Priority**         | P1                                 |
|------------------------------|-------------------------------------------|----------------------|------------------------------------|
| **Depends on**               | T06                                       | **Estimated scope**  | Large                              |
| **Primary deliverable**      | Checkpoint store and pause-resume example | **Tutorial concept** | State, interruption and resumption |
| **Required execution modes** | Offline                                   | **Paper relevance**  | Sections 3 and 7                   |

**Objective.** Add crash-resilient execution persistence without
conflating state with long-term memory.

**Implementation scope.**

- Define a CheckpointStore protocol.

- Implement JSON-file and SQLite checkpoint stores.

- Persist state after each completed step using atomic writes.

- Support resume by run identifier and validate schema versions.

- Demonstrate a deliberate interruption and resumption.

**Non-goals and exclusions.**

- Do not add semantic or vector memory.

**Acceptance criteria.**

- A run resumed from a checkpoint produces the same final logical result
  as an uninterrupted run.

- Corrupt checkpoints fail with explicit diagnostics.

- Checkpoint state does not contain plaintext API keys.

**Required tests.**

- Pause-resume integration test.

- Atomic-write recovery test.

- Schema mismatch test.

**Reproducibility evidence.**

- Checkpoint fixture and resume trace included.

- Storage format documented.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T08 Implement bounded execution, budgets and circuit breakers

| **Epic**                     | Safety core                                 | **Priority**         | P0                                |
|------------------------------|---------------------------------------------|----------------------|-----------------------------------|
| **Depends on**               | T01,T06                                     | **Estimated scope**  | Large                             |
| **Primary deliverable**      | Reusable BudgetManager and circuit breakers | **Tutorial concept** | Safe termination and cost control |
| **Required execution modes** | Offline and live-capable                    | **Paper relevance**  | Sections 3, 6 and 7               |

**Objective.** Guarantee that all iterative examples have deterministic
operational limits.

**Implementation scope.**

- Track model calls, tool calls, estimated or reported tokens, elapsed
  time and optional monetary cost.

- Implement pre-action and post-action budget checks.

- Detect repeated identical actions and short cycles.

- Define termination reasons for each exceeded budget.

- Allow stricter per-agent limits inside multi-agent workflows.

**Non-goals and exclusions.**

- Do not infer exact provider cost when reliable pricing metadata is
  unavailable.

**Acceptance criteria.**

- Every loop uses the shared budget manager.

- Budget exhaustion terminates cleanly and appears in state and trace.

- Repeated-action detection is covered by tests.

- Unknown monetary cost does not disable other limits.

**Required tests.**

- Unit tests for each limit.

- Short-cycle detection tests.

- Nested budget tests.

**Reproducibility evidence.**

- Budget configuration stored with each run.

- Trace records consumed and remaining budgets.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T09 Implement structured tracing and run manifests

| **Epic**                     | Observability                      | **Priority**         | P0                               |
|------------------------------|------------------------------------|----------------------|----------------------------------|
| **Depends on**               | T01,T05,T08                        | **Estimated scope**  | Large                            |
| **Primary deliverable**      | JSONL event trace and run manifest | **Tutorial concept** | Traceability and reproducibility |
| **Required execution modes** | Offline and live                   | **Paper relevance**  | Sections 3, 6 and 7              |

**Objective.** Create a framework-independent record of each execution
sufficient for debugging and scientific evaluation.

**Implementation scope.**

- Define trace events for run start, model request/response, tool
  request/result, state transition, human decision, error, checkpoint
  and termination.

- Write append-only JSONL traces with run identifiers and monotonic
  sequence numbers.

- Create a run manifest containing code version, dependency versions,
  configuration hash, schema version and environment metadata.

- Provide sanitisation hooks for secrets and sensitive content.

- Offer a trace reader for evaluation.

**Non-goals and exclusions.**

- Do not log private chain-of-thought; record operational decisions and
  structured outputs only.

**Acceptance criteria.**

- A complete run can be reconstructed at the level of actions and state
  transitions.

- Secrets in configured redaction tests do not appear in traces.

- All framework implementations emit the same canonical event types.

**Required tests.**

- Trace ordering tests.

- Sanitisation tests.

- Manifest completeness test.

- Round-trip trace reader test.

**Reproducibility evidence.**

- Example trace and manifest committed.

- Configuration hash documented.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T10 Create the progressive components tutorial

| **Epic**                     | Core tutorial                        | **Priority**         | P1                |
|------------------------------|--------------------------------------|----------------------|-------------------|
| **Depends on**               | T06,T07,T08,T09                      | **Estimated scope**  | Large             |
| **Primary deliverable**      | Series of component-focused examples | **Tutorial concept** | System components |
| **Required execution modes** | Offline and optional live            | **Paper relevance**  | Section 3         |

**Objective.** Build a coherent sequence showing how a minimal agent
becomes a stateful, controllable research assistant.

**Implementation scope.**

- Create separate runnable examples for tool use, explicit state,
  context management, planning, critique, human approval, checkpointing
  and recovery.

- Each example must reuse the same underlying task and state schemas.

- Each README must state the single new capability and concepts
  intentionally deferred.

- Keep visible files small by importing shared infrastructure.

**Non-goals and exclusions.**

- Do not turn examples into a single opaque application.

**Acceptance criteria.**

- Each example runs independently in mock mode.

- The delta from the previous example is clear and limited.

- Examples produce comparable traces.

- No example duplicates shared tool or provider code.

**Required tests.**

- Offline smoke test for every example.

- Expected-output fixture test.

- At least one failure-path test per major capability.

**Reproducibility evidence.**

- Commands and expected outputs documented.

- Trace fixtures versioned.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T11 Implement human-in-the-loop approval and resumption

| **Epic**                     | Core tutorial                                | **Priority**         | P1                  |
|------------------------------|----------------------------------------------|----------------------|---------------------|
| **Depends on**               | T07,T09                                      | **Estimated scope**  | Medium              |
| **Primary deliverable**      | Approval interface and resumable CLI example | **Tutorial concept** | Human oversight     |
| **Required execution modes** | Offline                                      | **Paper relevance**  | Sections 3, 4 and 7 |

**Objective.** Demonstrate a meaningful approval boundary before a
consequential or simulated side-effecting action.

**Implementation scope.**

- Define HumanDecision schema with approve, reject, edit and
  request-information outcomes.

- Pause execution by checkpointing a pending action.

- Provide a CLI approval interface and a programmatic decision provider
  for tests.

- Resume with an auditable state transition.

- Use a simulated side-effecting tool such as “prepare final
  submission”, not a real external action.

**Non-goals and exclusions.**

- Do not send real messages or modify external systems.

**Acceptance criteria.**

- No pending consequential action executes without approval.

- Reject and edit paths are implemented, not only approve.

- Automated tests do not require interactive input.

**Required tests.**

- Approve, reject and edit integration tests.

- Resume-after-decision test.

**Reproducibility evidence.**

- Human decision recorded in trace.

- README includes screenshots only if useful, but command-line text
  remains sufficient.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T12 Implement key execution patterns

| **Epic**                     | Patterns                            | **Priority**         | P1                      |
|------------------------------|-------------------------------------|----------------------|-------------------------|
| **Depends on**               | T05,T08,T09,T10                     | **Estimated scope**  | Extra large             |
| **Primary deliverable**      | Six self-contained pattern examples | **Tutorial concept** | Execution flow patterns |
| **Required execution modes** | Offline and optional live           | **Paper relevance**  | Section 4               |

**Objective.** Implement a deliberately limited set of patterns using
shared infrastructure and consistent tasks.

**Implementation scope.**

- Implement prompt chaining, routing, parallelisation, ReAct-style tool
  use, planner-executor, critic-reviser and one orchestrator-worker or
  supervisor-specialist example.

- Use one-line conceptual summaries and compact diagrams in README
  files.

- Keep pattern-specific control flow visible and avoid hiding it in
  utilities.

- Use deterministic fixtures to demonstrate routing and parallel result
  aggregation.

- Integrate human approval only where naturally relevant.

**Non-goals and exclusions.**

- Do not implement every pattern mentioned in surveys.

- Do not duplicate the components tutorial.

**Acceptance criteria.**

- Each pattern has one suitable use case and one demonstrated
  limitation.

- Pattern examples share schemas, tools, budgets and tracing.

- Parallel examples preserve deterministic output ordering.

- Planner and critic loops have explicit stopping rules.

**Required tests.**

- Pattern-specific integration tests.

- Failure or limitation fixture for every pattern.

- Deterministic concurrency test.

**Reproducibility evidence.**

- Expected traces and diagrams stored.

- Pattern-to-paper mapping documented.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T13 Specify the common research-assistant case study

| **Epic**                     | Case study                                                | **Priority**         | P0                       |
|------------------------------|-----------------------------------------------------------|----------------------|--------------------------|
| **Depends on**               | T01,T05                                                   | **Estimated scope**  | Large                    |
| **Primary deliverable**      | Versioned task specification, dataset and expected output | **Tutorial concept** | Common experimental task |
| **Required execution modes** | Offline                                                   | **Paper relevance**  | Sections 3, 5 and 6      |

**Objective.** Define a narrow, reproducible research-assistant task
that exercises agentic behaviour without becoming a full literature
review system.

**Implementation scope.**

- Create a small local catalogue of papers and metadata with
  deliberately relevant, irrelevant, conflicting and malformed entries.

- Define the task: formulate a plan, search the local catalogue, extract
  evidence, synthesise a concise answer, obtain critique and produce a
  structured final report.

- Define fixed inclusion criteria, success criteria and evidence
  requirements.

- Create easy, ambiguous and failure-injection task variants.

- Provide expected evidence sets and scoring annotations.

**Non-goals and exclusions.**

- Do not use live web search as the primary evaluation source.

- Do not attempt systematic review completeness.

**Acceptance criteria.**

- The task can be executed entirely offline.

- Ground truth is explicit enough for automated evaluation.

- The task requires multiple steps and tools but remains understandable
  to non-specialists.

- No copyrighted full paper text is redistributed.

**Required tests.**

- Dataset integrity tests.

- Ground-truth consistency tests.

- Task-variant loading tests.

**Reproducibility evidence.**

- Dataset version and licence notes included.

- Task specification hash recorded in manifests.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T14 Build the complete plain-Python case-study baseline

| **Epic**                     | Case study                                 | **Priority**         | P1                                      |
|------------------------------|--------------------------------------------|----------------------|-----------------------------------------|
| **Depends on**               | T10,T11,T12,T13                            | **Estimated scope**  | Large                                   |
| **Primary deliverable**      | End-to-end plain-Python research assistant | **Tutorial concept** | Framework-free reference implementation |
| **Required execution modes** | Offline and optional live                  | **Paper relevance**  | Sections 3, 5 and 6                     |

**Objective.** Provide the transparent reference implementation against
which framework abstractions are compared.

**Implementation scope.**

- Compose planning, routing, tools, state, critique, approval, tracing,
  budgets and checkpointing.

- Keep orchestration code explicit and documented.

- Support deterministic mock, replay and configured live model modes.

- Produce the common FinalAnswer schema and evidence table.

**Non-goals and exclusions.**

- Do not optimise for minimal lines of code at the expense of clarity.

**Acceptance criteria.**

- Completes all standard task variants in mock mode.

- Produces canonical traces and evaluation outputs.

- No framework dependency is imported.

- All loops and approvals are bounded.

**Required tests.**

- End-to-end success tests.

- Injected tool-failure recovery test.

- Ambiguous-task escalation test.

- Budget termination test.

**Reproducibility evidence.**

- Baseline traces and metrics committed.

- Exact commands documented.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T15 Implement the LangGraph version of the case study

| **Epic**                     | Frameworks                                     | **Priority**         | P1                                 |
|------------------------------|------------------------------------------------|----------------------|------------------------------------|
| **Depends on**               | T14                                            | **Estimated scope**  | Large                              |
| **Primary deliverable**      | LangGraph orchestration adapter and case study | **Tutorial concept** | Graph-based stateful orchestration |
| **Required execution modes** | Offline and optional live                      | **Paper relevance**  | Section 5                          |

**Objective.** Reimplement the common case study using LangGraph while
preserving shared behaviour and interfaces.

**Implementation scope.**

- Use shared schemas, tools, provider interface, budgets and trace
  events.

- Express nodes, conditional edges, loops, checkpointing and human
  interruption using LangGraph-native constructs where appropriate.

- Keep framework glue isolated in frameworks/langgraph and
  case_study/langgraph.

- Document semantic differences from the plain-Python baseline.

**Non-goals and exclusions.**

- Do not claim behavioural equivalence where framework semantics differ;
  document differences.

**Acceptance criteria.**

- Produces the same FinalAnswer schema and comparable canonical trace.

- Uses the same task fixtures and evaluation harness.

- Framework-specific code does not fork shared tools or prompts.

- Offline tests run with the deterministic model client.

**Required tests.**

- Matched-task integration tests.

- Checkpoint and interruption tests.

- Trace-schema compatibility tests.

**Reproducibility evidence.**

- Framework version pinned.

- Comparison notes recorded.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T16 Implement the CrewAI version of the case study

| **Epic**                     | Frameworks                       | **Priority**         | P2                                   |
|------------------------------|----------------------------------|----------------------|--------------------------------------|
| **Depends on**               | T14                              | **Estimated scope**  | Large                                |
| **Primary deliverable**      | CrewAI case-study implementation | **Tutorial concept** | Role-based multi-agent orchestration |
| **Required execution modes** | Offline and optional live        | **Paper relevance**  | Section 5                            |

**Objective.** Reimplement the common case study using CrewAI to
illustrate role-based abstraction and collaborative task execution.

**Implementation scope.**

- Map coordinator, researcher and critic responsibilities to framework
  abstractions.

- Reuse shared tools and final schemas through adapters.

- Control delegation and iteration using repository budgets.

- Normalise framework events into canonical trace events where possible.

- Document any framework features that cannot be disabled or matched
  exactly.

**Non-goals and exclusions.**

- Do not redesign the task to suit the framework.

**Acceptance criteria.**

- Same task fixtures and evaluation harness are used.

- Output conforms to the common FinalAnswer schema.

- Offline deterministic testing is possible; where the framework resists
  this, provide a narrow test adapter and document the limitation.

- No duplicated tools or dataset.

**Required tests.**

- Matched-task integration tests.

- Delegation-loop limit test.

- Trace normalisation tests.

**Reproducibility evidence.**

- Framework version pinned.

- Known comparison caveats documented.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T17 Implement the OpenAI Agents SDK version

| **Epic**                     | Frameworks                                  | **Priority**         | P2                                            |
|------------------------------|---------------------------------------------|----------------------|-----------------------------------------------|
| **Depends on**               | T14                                         | **Estimated scope**  | Large                                         |
| **Primary deliverable**      | OpenAI Agents SDK case-study implementation | **Tutorial concept** | Tools, handoffs and lightweight orchestration |
| **Required execution modes** | Mocked offline and optional live            | **Paper relevance**  | Section 5                                     |

**Objective.** Reimplement the common case study using the OpenAI Agents
SDK while retaining the repository’s provider-independent evaluation
surface.

**Implementation scope.**

- Use SDK agents, tools and handoffs where they naturally map to the
  case study.

- Wrap or adapt shared tools rather than recreate them.

- Translate SDK traces or lifecycle hooks into canonical events.

- Ensure tests can run with mocked provider calls even if live execution
  requires OpenAI.

- Document the boundary between the generic ModelClient abstraction and
  SDK-specific runtime.

**Non-goals and exclusions.**

- Do not force all tutorials to depend on this SDK.

**Acceptance criteria.**

- Offline tests require no OpenAI credential.

- Final output and metrics conform to common schemas.

- Live mode is explicit and optional.

- SDK-specific constraints are documented rather than hidden.

**Required tests.**

- Mocked handoff tests.

- Tool mapping tests.

- Optional live smoke test.

**Reproducibility evidence.**

- SDK and model versions recorded.

- Provider-specific caveats included in framework comparison.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T18 Select and implement an optional fourth framework

| **Epic**                     | Frameworks                            | **Priority**         | P3                                    |
|------------------------------|---------------------------------------|----------------------|---------------------------------------|
| **Depends on**               | T15,T16,T17                           | **Estimated scope**  | Large                                 |
| **Primary deliverable**      | One additional matched implementation | **Tutorial concept** | Breadth across a distinct abstraction |
| **Required execution modes** | Offline where feasible                | **Paper relevance**  | Section 5 supplementary material      |

**Objective.** Add a fourth framework only if it contributes a genuinely
distinct orchestration abstraction and remains actively supported.

**Implementation scope.**

- Evaluate Google ADK, Microsoft Agent Framework, LlamaIndex Workflows
  or another stable candidate using documented selection criteria.

- Record evidence on maintenance status, abstraction, offline
  testability and educational value.

- Implement the same case study without changing task requirements.

- Place this implementation in supplementary material if paper space is
  limited.

**Non-goals and exclusions.**

- Do not add a fourth framework merely for numerical breadth.

**Acceptance criteria.**

- A written selection decision precedes implementation.

- Framework adds a distinct conceptual perspective.

- Common evaluation and output schemas are preserved.

- If no candidate meets criteria, close the ticket with a justified
  no-implementation decision.

**Required tests.**

- Matched-task tests if implemented.

- Dependency conflict check.

**Reproducibility evidence.**

- Selection memo and framework version recorded.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T19 Build the common evaluation harness

| **Epic**                     | Evaluation                                   | **Priority**         | P0                           |
|------------------------------|----------------------------------------------|----------------------|------------------------------|
| **Depends on**               | T09,T13,T14                                  | **Estimated scope**  | Extra large                  |
| **Primary deliverable**      | Metrics, experiment runner and result schema | **Tutorial concept** | Multi-level agent evaluation |
| **Required execution modes** | Offline and live-capable                     | **Paper relevance**  | Section 6                    |

**Objective.** Create one evaluation system that scores components,
trajectories, outcomes and resource use across all implementations.

**Implementation scope.**

- Implement metrics for task success, evidence precision/recall, route
  correctness, tool-call validity, unnecessary actions, repeated
  actions, failure recovery, human intervention, latency, calls and
  tokens.

- Define experiment configuration and repeated-run support.

- Compare direct LLM, plain-Python agent and framework implementations
  where applicable.

- Separate deterministic benchmark metrics from optional LLM-as-judge
  metrics.

- Produce machine-readable results and concise summary tables.

**Non-goals and exclusions.**

- Do not use final-answer quality alone as the success criterion.

- Do not present LLM-as-judge as objective ground truth.

**Acceptance criteria.**

- All implementations can be evaluated through the same entry point.

- Metrics have documented definitions and edge-case behaviour.

- Deterministic metrics do not require a live model.

- Missing provider usage data is represented explicitly, not as zero.

**Required tests.**

- Metric unit tests.

- Known-trajectory scoring tests.

- Repeated-run aggregation tests.

- Result serialisation tests.

**Reproducibility evidence.**

- Benchmark task, code revision and configuration hash recorded.

- Raw traces retained alongside aggregate results.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T20 Create controlled failure and adversarial scenarios

| **Epic**                     | Evaluation and safety   | **Priority**         | P1                            |
|------------------------------|-------------------------|----------------------|-------------------------------|
| **Depends on**               | T13,T19                 | **Estimated scope**  | Large                         |
| **Primary deliverable**      | Failure-injection suite | **Tutorial concept** | Robustness and safety testing |
| **Required execution modes** | Offline                 | **Paper relevance**  | Sections 6 and 7              |

**Objective.** Test whether examples fail safely and recover
appropriately under realistic operational faults.

**Implementation scope.**

- Add scenarios for malformed tool arguments, transient tool failure,
  contradictory evidence, prompt injection in retrieved text, repeated
  model action, context overflow proxy, unavailable tool and critic
  disagreement.

- Label expected recovery or termination behaviour for each scenario.

- Ensure injected content cannot alter system or tool permissions.

- Support deterministic replay of each failure.

**Non-goals and exclusions.**

- Do not include harmful operational payloads; use benign simulated
  attacks.

**Acceptance criteria.**

- Every scenario has an expected outcome classification.

- Unsafe requests do not execute side effects.

- Failure traces identify the source and recovery path.

- At least one scenario distinguishes single-agent from multi-agent
  error propagation.

**Required tests.**

- Scenario-specific integration tests.

- Prompt-injection boundary test.

- Repeated-loop circuit-breaker test.

**Reproducibility evidence.**

- Failure fixtures versioned.

- Expected outcomes documented.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T21 Add safety validators and permission policies

| **Epic**                     | Safety core                                  | **Priority**         | P1                             |
|------------------------------|----------------------------------------------|----------------------|--------------------------------|
| **Depends on**               | T05,T08,T20                                  | **Estimated scope**  | Large                          |
| **Primary deliverable**      | Policy engine for tool and output validation | **Tutorial concept** | Guardrails and least privilege |
| **Required execution modes** | Offline                                      | **Paper relevance**  | Section 7                      |

**Objective.** Provide deterministic controls around model-proposed
actions and final outputs.

**Implementation scope.**

- Define tool permission levels and per-agent allowlists.

- Validate tool arguments, output schemas, evidence citations and
  prohibited action classes.

- Implement approval requirements for simulated consequential actions.

- Define policy decisions as allow, deny, require approval or transform.

- Record every policy decision in traces.

**Non-goals and exclusions.**

- Do not implement vague “AI safety scoring” as a substitute for
  deterministic controls.

**Acceptance criteria.**

- Denied actions never reach tool execution.

- Policies are testable independently of model behaviour.

- Framework adapters use the same policy engine.

- Default policy is least privilege.

**Required tests.**

- Allow/deny/approval tests.

- Framework adapter policy test.

- Policy trace test.

**Reproducibility evidence.**

- Policy version included in manifests.

- Example policy configuration committed.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T22 Create documentation and teaching consistency checks

| **Epic**                     | Documentation                                        | **Priority**         | P1                                  |
|------------------------------|------------------------------------------------------|----------------------|-------------------------------------|
| **Depends on**               | T10,T12,T14-T21                                      | **Estimated scope**  | Large                               |
| **Primary deliverable**      | Consistent READMEs, diagrams and tutorial navigation | **Tutorial concept** | Learnability and conceptual clarity |
| **Required execution modes** | Offline                                              | **Paper relevance**  | All paper sections                  |

**Objective.** Ensure that repository organisation teaches the concepts
progressively and consistently.

**Implementation scope.**

- Create a documentation template containing objective, prerequisites,
  architecture, command, expected output, new concept, exclusions,
  failure case and next step.

- Add a repository learning path matching paper Sections 2 to 7.

- Create compact Mermaid or equivalent diagrams for components and
  patterns.

- Add a glossary distinguishing state, context, memory, planning,
  routing, orchestration, agent and workflow.

- Implement a script that checks required README headings and broken
  relative links.

**Non-goals and exclusions.**

- Do not repeat generic LLM or RAG tutorials.

**Acceptance criteria.**

- Every tutorial and pattern follows the template.

- Terminology is used consistently across documentation.

- Commands are executable from repository root.

- Diagrams render from source text.

**Required tests.**

- Documentation structure test.

- Link check.

- Command extraction smoke test where feasible.

**Reproducibility evidence.**

- Documentation build command recorded.

- Glossary versioned.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T23 Create the framework comparison experiment

| **Epic**                     | Evaluation                                        | **Priority**         | P1                        |
|------------------------------|---------------------------------------------------|----------------------|---------------------------|
| **Depends on**               | T15,T16,T17,T19                                   | **Estimated scope**  | Large                     |
| **Primary deliverable**      | Matched experimental comparison and caveat report | **Tutorial concept** | Fair framework comparison |
| **Required execution modes** | Offline plus limited live                         | **Paper relevance**  | Sections 5 and 6          |

**Objective.** Run a scientifically defensible comparison focused on
orchestration properties rather than declaring an overall winner.

**Implementation scope.**

- Define matched configurations for model, prompts, task variants,
  budgets and repetitions.

- Measure implementation-facing properties separately from runtime
  performance.

- Report lines of orchestration code cautiously and exclude shared
  infrastructure.

- Capture framework-specific semantic differences and missing features.

- Run deterministic offline comparisons and a small, clearly labelled
  live validation if feasible.

**Non-goals and exclusions.**

- Do not compare different models under different frameworks.

- Do not treat fewer lines of code as superior quality.

**Acceptance criteria.**

- Comparison uses identical task fixtures and evaluation definitions.

- Results include uncertainty or run-to-run variation where live models
  are used.

- No overall composite ranking is produced without a justified weighting
  scheme.

- Limitations and non-equivalences are explicit.

**Required tests.**

- Experiment configuration validation.

- Result reproducibility test for offline mode.

**Reproducibility evidence.**

- All configs, traces and result tables retained.

- Code revision and environment manifest attached.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

## T24 Establish continuous integration and release reproducibility

| **Epic**                     | Release engineering                                   | **Priority**         | P1                          |
|------------------------------|-------------------------------------------------------|----------------------|-----------------------------|
| **Depends on**               | T00-T23                                               | **Estimated scope**  | Large                       |
| **Primary deliverable**      | CI pipeline, release checklist and archived artefacts | **Tutorial concept** | Sustainable reproducibility |
| **Required execution modes** | Offline                                               | **Paper relevance**  | Supports paper artefact     |

**Objective.** Ensure the repository remains runnable despite rapidly
changing agent frameworks.

**Implementation scope.**

- Create CI jobs for lint, type checking, unit tests, offline
  integration tests and documentation checks.

- Use dependency groups so framework jobs are isolated where necessary.

- Create a compatibility matrix for Python and framework versions.

- Add a release script that exports environment manifests and benchmark
  fixtures.

- Document upgrade policy and deprecation handling.

**Non-goals and exclusions.**

- Do not continuously chase latest versions without a scheduled
  compatibility review.

**Acceptance criteria.**

- Core offline CI passes without credentials.

- Framework-specific dependency conflicts are isolated.

- A tagged release can recreate the documented environment.

- Live tests are never run automatically without explicit secrets and
  flags.

**Required tests.**

- Fresh-environment installation test.

- Matrix smoke tests.

- Release artefact validation.

**Reproducibility evidence.**

- Lock files and compatibility matrix archived per release.

- Benchmark traces tied to release tag.

**Instructions for the coding model.**

- Inspect existing repository interfaces before writing code; extend
  rather than duplicate them.

- Do not add a new dependency unless it is necessary and recorded in
  pyproject.toml and the lock file.

- Use UK English in documentation and comments.

- Run formatting, type checking and the ticket-specific tests before
  completion.

- Return a concise summary of changed files, commands run, test results
  and unresolved limitations.

# 8. Coding-model hand-off template

Use the following prompt when assigning an individual ticket to Codex or
another coding model. Attach this backlog and identify the ticket
explicitly.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th>Implement ticket [TICKET ID] from the Agentic AI Tutorial Repository
backlog.<br />
<br />
Before coding:<br />
1. Inspect the current repository and the ticket dependencies.<br />
2. Summarise the existing interfaces you will reuse.<br />
3. Identify any conflict between the repository and the ticket. Preserve
established contracts unless the ticket explicitly changes them.<br />
<br />
Implementation requirements:<br />
- Implement only the stated scope and acceptance criteria.<br />
- Keep provider-independent logic outside vendor and framework
adapters.<br />
- Reuse shared schemas, tools, budgets, tracing and evaluation
infrastructure.<br />
- Preserve deterministic mock or replay execution.<br />
- Add the required tests and documentation.<br />
- Do not introduce side-effecting tools or paid-API requirements.<br />
- Pin and document any new dependency.<br />
<br />
Before completion, run the relevant formatting, linting, type checking
and tests. Report changed files, commands run, test results, design
decisions and any unmet acceptance criterion. Do not claim completion if
any criterion is missing.</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

# 9. Decisions to preserve during development

- The primary case study is a narrow, offline-capable research
  assistant, not an autonomous systematic-review system.

- The paper will cover a limited set of key execution patterns; the
  repository may contain additional examples only when they remain
  clearly labelled and maintained.

- Plain Python is the reference implementation. Framework versions are
  alternative orchestration expressions, not separate applications.

- Three principal frameworks are sufficient. A fourth is optional and
  must earn inclusion through a distinct abstraction and stable support.

- API independence does not mean pretending all providers are identical.
  Normalise common capabilities and document semantic differences.

- Evaluation must score execution trajectories and operational
  properties as well as final outputs.

- The repository should favour clarity over premature production
  complexity, while retaining typed interfaces, bounded execution, tests
  and traces.
