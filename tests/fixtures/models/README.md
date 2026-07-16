# Offline model fixtures

All fixtures in this directory are canonical, versioned and safe to commit.

- `mock/scenario_v1.json` is hand-authored for deterministic tutorial and test execution. Responses are selected by scenario and consumed in step order.
- `replay/catalogue_v1.jsonl` is a sanitised canonical recording created for this repository. Its first line records fixture version and provenance; subsequent lines pair canonical requests with canonical responses.
- `capability_matrix_v1.json` documents the common capabilities expected from minimal and scripted offline clients.

Replay files contain no provider SDK objects, credentials or private chain-of-thought. A change to messages, tools, response schema or generation settings is a mismatch and must be recorded as a new fixture version rather than accepted silently.
