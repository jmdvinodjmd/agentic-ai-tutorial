# Glossary

| Term | Meaning in this repository |
|---|---|
| Agent | A bounded process that uses a model to select canonical actions, updates explicit state and terminates explicitly. |
| Context | Information supplied to the model for the current decision, including retained messages. |
| Memory | Information deliberately persisted for later retrieval; it is distinct from current context and checkpoint state. |
| State | The canonical serialisable record of task, messages, steps, usage, errors, pending actions and termination. |
| Checkpoint | A durable snapshot used to resume execution without repeating completed work. |
| Tool | A validated interface through which an agent can observe or affect an environment under a permission policy. |
| Planning | Explicit decomposition of a task into bounded steps before or during execution. |
| Routing | Selection of the next branch, worker or specialist from explicit alternatives. |
| Orchestration | Coordination of state transitions, model calls, tools, routing, checkpoints and termination. |
| Workflow | A defined execution flow; it may be deterministic and does not necessarily contain an autonomous agent loop. |
| System component | A reusable part such as a model client, tool registry, state schema, budget or tracer. |
| Execution pattern | A recurring arrangement of components, such as prompt chaining or planner-executor. |
| Framework abstraction | A framework-specific way to express orchestration while retaining the common task and contracts. |
| Mock | Deterministic scripted model behaviour used for teaching and automated comparison. |
| Replay | Strict playback that returns a recorded response only when the current canonical request matches. |
