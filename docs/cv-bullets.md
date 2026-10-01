# CV bullets

- Built a framework-independent operations agent with FastAPI, PostgreSQL, local
  Ollama and MCP, using seven typed read-only capabilities and bounded orchestration
  with recoverable tool errors.
- Designed two MCP v2 servers for relational analytics and policy retrieval, with
  dynamic capability discovery, ownership routing, duplicate-name rejection and
  no unrestricted SQL access.
- Evaluated 16 tool-selection, eight policy-retrieval and 13 end-to-end agent cases:
  16/16 selection, 8/8 retrieval and 12/13 agent tool-behavior checks, documenting
  the remaining dependent-ID grounding failure rather than hiding it.
- Containerized React/FastAPI/PostgreSQL with an nginx NDJSON streaming proxy,
  persistent database storage and host Ollama connectivity, preserving observable
  tool traces and request cancellation/resource cleanup.

These describe a synthetic-data local portfolio project, not production traffic
or deployed customer usage. See [evaluation](evaluation.md) for metric scope.
