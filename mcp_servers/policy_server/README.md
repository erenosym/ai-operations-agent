# Operations policy MCP server

`operations-policy` exposes one read-only stdio tool, `search_policy`. It searches
only the three known synthetic Markdown files in `policies/`; callers cannot supply
paths or read arbitrary files. Retrieval is deterministic lexical matching, not
embedding or vector search.

From the repository root:

```shell
PYTHONPATH=.:backend backend/.venv/bin/python -m mcp_servers.policy_server.server
```
