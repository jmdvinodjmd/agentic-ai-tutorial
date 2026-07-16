# Shared safety policy

The deterministic safety engine applies one versioned policy before canonical tool execution. It intersects the policy allowlist with the current agent allowlist, validates arguments through the registered tool schema, enforces side-effect classifications and requires approval tokens bound to the exact tool name, call identifier and arguments.

Retrieved text remains in tool/data messages and never becomes a system or task instruction. A small indicator list flags common instruction-like phrases and records a canonical `policy_decision` trace event, but detection is not a complete security guarantee. Applications must retain role separation, least privilege, output provenance checks, bounded execution and human escalation for consequential uncertainty.

Policy outcomes are `allow`, `deny`, `require_approval`, `transform` and `escalate`. Denied actions never reach handlers. The policy version is recorded in case-study manifests; budgets and repeated-action detection continue to use the single shared `BudgetManager`.
