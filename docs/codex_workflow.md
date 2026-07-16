# Step-by-step Codex Workflow

This file provides prompts to use in the Codex VS Code extension. Keep `AGENTS.md` at the repository root and `implementation_backlog.md` under `docs/`.

## Step 0: Open the correct folder

Open the empty repository folder itself in VS Code, not its parent directory. Confirm that Codex can see:

```text
AGENTS.md
docs/implementation_backlog.md
```

Initial expected structure:

```text
repository-root/
├── AGENTS.md
└── docs/
    └── implementation_backlog.md
```

## Step 1: Ask Codex to audit and plan only

Use this prompt before permitting code changes:

```text
Read AGENTS.md and docs/implementation_backlog.md in full. Inspect the current repository.

Do not create or edit implementation files yet.

Produce a dependency-aware execution plan for the backlog. Confirm:
1. the proposed repository structure;
2. the shared framework-independent layer;
3. the framework-specific orchestration layer;
4. the offline mock and replay strategy;
5. the testing and reproducibility strategy;
6. the first ticket that should be implemented.

Identify contradictions, missing prerequisites, decisions that can be deferred, and any point that could cause provider lock-in or invalidate framework comparisons. Follow the defaults in AGENTS.md rather than inventing alternatives.
```

Review the plan. It should recommend T00 first and should not propose implementing the whole repository at once.

## Step 2: Implement T00 only

```text
Implement only Ticket T00 from docs/implementation_backlog.md.

Follow AGENTS.md. Create the repository scaffold, pyproject.toml, uv configuration and lock file, package initialisation, developer commands, root README, .env.example, and the offline smoke-test entry point required by T00.

Do not implement agent logic, provider adapters or framework integrations.

Before completion, run the required installation, import, CLI-help, formatting, linting and type-check checks. Report changed files, commands, results and any unmet acceptance criterion.
```

After review, create a Git checkpoint.

## Step 3: Review T00 before proceeding

```text
Audit the current repository only against Ticket T00 and AGENTS.md. Do not modify files initially.

Check packaging, uv.lock, src layout, commands, documentation, offline execution, dependency minimality and UK English. Identify any incomplete acceptance criterion or premature implementation of later tickets.

If defects are found, fix only those defects, rerun the checks and report the final status.
```

## Step 4: Implement foundation tickets one at a time

Use the reusable ticket prompt below in this order:

1. T01 canonical schemas
2. T02 provider-independent model interface
3. T03 deterministic mock and replay clients
4. T05 shared tool registry and safe executor
5. T06 minimal plain-Python agent loop
6. T07 persistence and checkpointing
7. T08 budgets and circuit breakers
8. T09 tracing and run manifests

T04, the live-provider adapter, can be deferred until the offline foundation is stable.

### Reusable ticket prompt

```text
Implement only Ticket [TICKET_ID] from docs/implementation_backlog.md.

Before coding:
1. read AGENTS.md and the full ticket;
2. inspect the current repository and ticket dependencies;
3. summarise the interfaces and files that will be reused;
4. identify any conflict with established contracts.

Implementation requirements:
- implement only the ticket scope and explicit prerequisites;
- preserve provider independence;
- reuse shared schemas, tools, budgets and tracing;
- keep deterministic offline execution working;
- add all required tests, fixtures, documentation and expected outputs;
- do not begin later tickets or perform unrelated refactoring.

Before completion, run formatting, linting, mypy, ticket-specific tests and relevant offline smoke tests.

Report changed files, design decisions, commands, test results, each acceptance criterion, and any unresolved issue. Do not claim completion if any criterion is unmet.
```

Replace `[TICKET_ID]` with the required identifier.

## Step 5: Conduct a foundation architecture audit

After T09:

```text
Perform an architecture audit of Tickets T00 to T09 against AGENTS.md and docs/implementation_backlog.md.

Do not modify code until you have reported findings.

Check specifically for:
- provider SDK objects leaking into shared schemas or state;
- API keys read outside provider construction;
- duplicated schemas or tools;
- non-deterministic offline tests;
- unbounded loops;
- incomplete error classifications;
- traces that cannot reconstruct a run;
- unnecessary dependencies;
- missing acceptance criteria.

Then fix confirmed defects only, rerun the full offline quality suite and report the result.
```

Create a Git checkpoint after acceptance.

## Step 6: Implement educational examples

Proceed one ticket at a time:

1. T10 progressive components tutorial
2. T11 human approval and resumption
3. T12 key execution patterns

For T12, retain only the key patterns specified in the ticket. Do not expand the scope into a catalogue of every published pattern.

After T12, ask Codex to verify that each tutorial introduces one principal concept and states what it deliberately excludes.

## Step 7: Freeze the common case study

Implement:

1. T13 common research-assistant specification
2. T14 complete plain-Python baseline

Use this additional instruction for T13:

```text
The case study must remain narrow and offline-capable. Use fixed local fixtures and deterministic tool outputs. It is not an autonomous systematic-review system and must not require web search, a vector database or a paid API in its default mode.
```

Do not start framework integrations until T14 is stable.

## Step 8: Freeze evaluation before framework implementations

Although the backlog groups framework implementations before evaluation, implement T19 immediately after T14. This locks the metrics and prevents framework-specific design from shaping the evaluation criteria.

Order:

1. T19 common evaluation harness
2. T20 controlled failure and adversarial scenarios
3. T21 safety validators and permission policies

Then run an audit confirming that the plain-Python baseline passes the same harness that later frameworks will use.

## Step 9: Add the first live provider only when needed

Implement T04 after the offline baseline and evaluation are stable.

Before assigning T04, decide which provider will be the first reference adapter. The adapter must be optional and must not change canonical schemas or tutorial logic.

Suggested prompt:

```text
Implement Ticket T04 using [SELECTED_PROVIDER] as the first reference live-provider adapter.

The provider SDK must remain confined to the adapter package. Map provider messages, tool calls, responses and usage into the canonical internal schemas. Do not expose provider objects through shared interfaces. Live tests must be opt-in and skip cleanly without credentials. Preserve deterministic mock and replay modes as the default.
```

Do not hard-code a specific model name. Load it from configuration with a documented example default.

## Step 10: Implement matched framework versions

Proceed individually:

1. T15 LangGraph
2. T16 CrewAI
3. T17 OpenAI Agents SDK

For every framework ticket, add this requirement:

```text
The framework implementation must reuse the exact common TaskSpec fixtures, prompts, tools, canonical final-output schema, budgets, stopping rules, safety policies and evaluation harness used by the plain-Python baseline. Framework-specific code should contain orchestration only. Document any semantic feature that cannot be made equivalent.
```

Do not implement T18 unless a fourth framework is later justified.

## Step 11: Run the matched comparison

Implement T23 after T15, T16, T17 and T19.

Require Codex to validate configuration equivalence before running comparisons. Do not allow a single overall framework ranking unless a defensible weighting scheme has been specified.

## Step 12: Complete documentation and release quality

Implement:

1. T22 documentation and teaching consistency
2. T24 CI and release reproducibility

T24 should run core offline CI without credentials. Live-provider tests must remain manual or explicitly gated by secrets and flags.

## Step 13: Optional fourth framework

Implement T18 only after the three principal framework versions and comparison are complete. Select a fourth framework only if it provides a genuinely distinct abstraction, has stable support and can use the same common contracts.

## Review prompt after every ticket

```text
Review the implementation of Ticket [TICKET_ID] against AGENTS.md and every acceptance criterion in docs/implementation_backlog.md.

First report findings without editing. Check for scope creep, conceptual mixing, provider lock-in, duplicated shared logic, non-determinism, unbounded execution, weak failure tests and incomplete documentation.

Then correct confirmed defects only, rerun all relevant checks and provide the final acceptance table.
```

## Git checkpoint recommendation

After each accepted ticket:

```bash
git status
git add .
git commit -m "Implement TXX: concise ticket description"
```

Do not ask Codex to implement all tickets in a single conversation. Start a fresh task or clearly reset context for each substantial ticket.
