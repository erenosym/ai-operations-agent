# Operations PostgreSQL MCP server

`operations-postgres` publishes read-only, structured operations-data capabilities over MCP. It delegates to the backend repository layer; it contains no business SQL.

Tools:

- `find_products`
- `get_customer_orders`
- `get_recent_refunds`
- `get_top_refunded_products`
- `get_product_statistics`
- `get_refund_reason_breakdown`

The development transport is stdio. From the repository root, run:

```shell
PYTHONPATH=.:backend DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations backend/.venv/bin/python -m mcp_servers.postgres_server.server
```

Use `postgres:5432` instead of `localhost:5432` inside Docker Compose. The server runs as an API-container subprocess and requires `DATABASE_URL`; it does not load or embed credentials itself.

For the official MCP v2 Inspector workflow, install `uv` and Node.js/npm, then run from the repository root:

```shell
PYTHONPATH=.:backend DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations backend/.venv/bin/mcp dev mcp_servers/postgres_server/server.py:mcp --with-editable backend
```

Invalid dates and repository validation failures become readable MCP tool errors. An unknown product returns `{"found": false, "product": null}`. Unexpected internal or database failures are kept generic at the protocol boundary.
