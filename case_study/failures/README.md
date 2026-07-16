# Controlled failure scenarios

The versioned offline fixture exercises malformed decisions, invalid and unauthorised tools, timeouts, recovery, circuit breakers, evidence limitations, untrusted retrieved text, checkpoint corruption, replay divergence and budget exhaustion. Every scenario declares whether the expected outcome is safe termination, recovery, denial or human escalation.

All actions are local and read-only. The prompt-injection fixture is benign simulated text: it remains separated as untrusted content and is never interpreted as a system or task instruction. The suite demonstrates deterministic boundaries, not complete protection against every adversarial prompt.
