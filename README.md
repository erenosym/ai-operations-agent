# AI Operations Agent

A local, MCP-powered e-commerce operations assistant combining PostgreSQL facts
with policy rules, with observable tool execution instead of hidden reasoning.
Built as a portfolio project: synthetic data, measured local evaluations, and
explicitly documented model failures—not a public production service.

The agent is driven by a small framework-independent harness built around
`AgentRuntime`, which manages the bounded execution loop, MCP tool discovery and
routing, structured observations, failures, and observable execution events.

## Problem

Operational questions span structured records and internal rules: which products
are refunded most, why, and whether the policy covers that reason. This project
lets a local model request narrow read-only capabilities, then synthesize their
observations without receiving arbitrary SQL or filesystem access.

## Demo

Primary prompt:

> Analyze the top 3 products by refund rate in September 2026. For the worst-performing product, identify the main refund reason and check whether the refund policy covers that situation.

Typical workflow: `get_top_refunded_products` → `get_refund_reason_breakdown`
→ `search_policy` → final synthesis. Actual execution remains model-driven;
the exact chain and correctly grounded follow-up arguments are not guaranteed.
The UI shows tool arguments, results, duration, policy sources, and cancellation.

Also try “What does the policy say about receiving a damaged item?” and “Hello.”
The latter requires no tool invocation, although per-run MCP connections still open.

## Architecture

Browser → nginx → FastAPI → AgentRuntime → Ollama / MCP clients.
`AgentRuntime` is the custom agent harness core: it owns orchestration, discovered
tool registration and MCP client routing, observations, failure handling,
termination, and observable events—not model reasoning.
Operations MCP → repository → PostgreSQL; policy MCP → lexical search → known
Markdown files. Ollama runs on the host; both stdio MCP servers run as subprocesses
inside the API container. See [architecture](docs/architecture.md) for the diagram,
request lifecycle, boundaries, and security qualifications.

## Tech Stack

React, TypeScript, Vite; FastAPI, Python 3.13 Docker runtime (package minimum 3.11);
official MCP Python SDK v2; PostgreSQL 17, async SQLAlchemy 2.x, asyncpg, Alembic;
local Ollama with qwen2.5:7b; Docker Compose and nginx.

## How the Agent Works

For each run, the custom harness discovers capabilities from both MCP servers,
validates their expected tool sets, rejects duplicate names, and maps each name
to its owning client.
It sends messages and discovered schemas through `LLMProvider` to the model,
which returns a final answer or one or more structured tool calls. The harness
checks each proposed name against the discovered allowlist, rejects unknown tools
before invocation, and routes allowed calls to their owning MCP clients.
Calls execute sequentially; structured results or recoverable tool errors become
observations in model context before the next model turn. A final answer ends the
loop; reaching `max_steps` terminates it with an error.
Default `max_steps` is 5 model turns; the API accepts 1–10. This bounds turns,
not wall-clock time or the total calls within a turn.
Infrastructure failures terminate safely; ordinary tool failures permit model-led
recovery within that bound. There are no automatic retries or persistent sessions.

The model proposes tool calls; the harness controls execution. Through
`run_stream()`, the harness emits observable `AgentEvents`: execution state, not
hidden model reasoning or chain-of-thought.

### Agent harness vs related concepts

| Concept | Role in this project |
| --- | --- |
| LLM | qwen2.5:7b generates responses and structured tool calls |
| LLM adapter | `OllamaProvider` implements `LLMProvider` and isolates provider-specific behavior |
| Agent harness | `AgentRuntime` and its orchestration/tool-execution boundary control multi-step execution |
| Tool calling | The model selects a typed capability and arguments |
| MCP client | Discovers and invokes MCP capabilities |
| MCP server | Publishes typed operational capabilities |
| Agent | The full model + harness + tools + context + execution-loop system |

## MCP Capabilities

| Server | Tool | Responsibility |
| --- | --- | --- |
| operations-postgres | `find_products` | Resolve product names/categories to IDs |
| operations-postgres | `get_customer_orders` | Bounded customer order history |
| operations-postgres | `get_recent_refunds` | Refund records with product/order context |
| operations-postgres | `get_top_refunded_products` | Ranked refund-rate analytics |
| operations-postgres | `get_product_statistics` | Sales/refund facts for one product ID |
| operations-postgres | `get_refund_reason_breakdown` | Reason counts and proportions |
| operations-policy | `search_policy` | Ranked policy sections with source metadata |

No unrestricted SQL capability is exposed. MCP schemas originate at the servers,
not a second hand-maintained schema registry in the agent.

## PostgreSQL Data Model

`customers` → `orders` → `order_items` → `refunds`, with `products` referenced
by order items. Tables use bigint identity primary keys, foreign keys with
`ON DELETE RESTRICT`, `NUMERIC(12,2)` money, timezone-aware timestamps, uniqueness
and check constraints, and date/status/FK lookup indexes. Alembic owns the schema;
application startup never calls `create_all()`.

Input date bounds are inclusive calendar dates in UTC. Internally, the end date
becomes the start of the following day for an exclusive timestamp comparison.
Refund rate is distinct refunded order items / sold order items for non-cancelled
orders in the selected order-date cohort, with refunds also requested in that
interval. It is a ratio, not a percentage; Decimal values cross MCP as strings.
See [query performance baseline](docs/query-performance.md).

### Reproducibility

Random seed: `20261001`; reference date: `2026-10-01`.
The deterministic dataset has 500 customers, 50 products, 2,000 orders, 5,877
order items, and 404 refunds. Intentional patterns: Pulse Wireless Headphones
high refund rate; StridePro Running Shoes elevated `size_issue` refunds;
Forge Mechanical Keyboard low-refund control.

Row values/patterns are deterministic; identity IDs can differ after `--reset`
because sequences are not reset. Resolve entities using returned IDs, not rank.
Python dependency ranges and Docker tags are not locked; this is not a bit-for-bit
reproducible build. The frontend uses its committed npm lockfile.

## Policy Retrieval

Three synthetic refund, return, and shipping documents are split into level-two
heading sections. Deterministic lexical ranking combines normalized phrase and
token overlap, with stable tie-breaking and an optional policy-type filter.
Results carry section, policy name, content, score, and source filename.
There are no embeddings or vector database; synonym handling is limited.

## Evaluation

| Evaluation | Cases | Result |
| --- | ---: | ---: |
| Tool selection | 16 | 16/16 |
| Policy retrieval | 8 | 8/8 |
| Agent completion | 13 | 13/13 |
| Agent answer checks | 13 | 13/13 |
| Agent tool behavior | 13 | 12/13 |

Results are from the project's deterministic local evaluation fixtures.
Model inference is not universally deterministic across versions/hardware.
Answer checks test required terms/source references, not exhaustive factual
correctness. One rank-as-ID dependent-grounding failure remains.
Evaluations separate tool selection, retrieval quality, and end-to-end harness/agent
behavior: selecting the right tool does not guarantee correctly grounded execution,
as the documented 12/13 agent tool-behavior result demonstrates.
See [evaluation scope and failure story](docs/evaluation.md).

## Docker Quick Start

Requires Docker Compose and host Ollama with `qwen2.5:7b` already installed.
Check with `ollama list`; Compose neither starts Ollama nor pulls the model.
From the repository root:

```shell
cp .env.example .env
docker compose config --quiet
docker compose build
docker compose up -d
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m scripts.seed_database
docker compose ps
```

Open http://localhost:5173. Skip seed on an already populated database; normal
seeding refuses to overwrite rows. Apply migrations before submitting tasks.
API health: http://localhost:8001/health or http://localhost:5173/api/health.

| Configuration | Default / meaning |
| --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Local example value `operations` |
| `DATABASE_URL` | Compose URL uses `postgres:5432`; synchronize credentials with `POSTGRES_*` |
| `OLLAMA_BASE_URL` | Host development: `http://localhost:11434` |
| `DOCKER_OLLAMA_BASE_URL` | Compose override: `http://host.docker.internal:11434` |
| `OLLAMA_MODEL` | `qwen2.5:7b` |
| `FRONTEND_ORIGIN` | Host development CORS: `http://localhost:5173` |
| `FRONTEND_PORT`, `API_PORT`, `POSTGRES_PORT` | Loopback host ports 5173, 8001, 5432 |

Container ports are 80, 8001, 5432. Stop conflicting host dev servers or change
published port variables. URL-encode reserved password characters in DATABASE_URL.
These example credentials are for local development only.

API waits for PostgreSQL health; frontend waits for API DB health. Health does not
verify migration/seed completion, Ollama, or MCP. Services use `unless-stopped`.
Migrations and seeds never run automatically. No host bind mounts are required.
Backend image is approximately 350 MB; nginx frontend approximately 92 MB
at the measured Docker checkpoint (sizes depend on base-image versions).

```shell
docker compose logs --tail=100 api frontend postgres
docker compose exec api alembic check
docker compose exec api python -m scripts.check_mcp_client
docker compose exec api python -m scripts.check_policy_mcp_client
docker compose down
docker compose up -d
```

`down` preserves `postgres_data`. **`docker compose down -v` permanently deletes
the database volume.** Only for an intentional development-data reset:

```shell
docker compose run --rm api python -m scripts.seed_database --reset
```

That deletes application rows; do not use it on important data.
For isolated verification, prefix every Compose command consistently with
`POSTGRES_PORT=15432 API_PORT=18001 FRONTEND_PORT=15173` and use
`docker compose -p operations-compose-check ...`; this selects a separate volume.

Docker Desktop host connectivity is verified on macOS. Linux includes a
host-gateway mapping but remains unverified; host Ollama may need to listen on a
Docker-reachable interface with deliberate firewall restrictions. Never expose it
publicly.

## Host Development

Use Python 3.13 and Node.js 24 to match the tested Docker build runtimes.
Compose reads root `.env`; Python does not automatically load it. Use explicit
environment variables for host processes. From the repository root:

```shell
docker compose up -d postgres
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e './backend[test]'
```

From `backend/`:

```shell
export DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=qwen2.5:7b
.venv/bin/alembic upgrade head
.venv/bin/alembic check
.venv/bin/python -m scripts.seed_database
FRONTEND_ORIGIN=http://localhost:5173 PYTHONPATH=.:.. \
  .venv/bin/uvicorn app.main:app --host localhost --port 8001
```

Skip seed if populated. From `frontend/`, in a separate terminal:

```shell
npm ci
npm run dev
```

Vite defaults to API `http://localhost:8001`; `frontend/.env.example` documents
the optional `VITE_API_BASE_URL` override. Vite variables are public, never secrets.

## API

`GET /health` returns DB `ok` or a useful `degraded` body (HTTP 200 in both
cases); Compose checks the body. `POST /agent/run` accepts a trimmed nonempty
`message` of at most 10,000 characters and optional integer `max_steps` (1–10).
OpenAPI is available at `/docs` on the API port.

```shell
curl --no-buffer -H 'Content-Type: application/json' \
  --data '{"message":"What does the policy say about receiving a damaged item?","max_steps":5}' \
  http://localhost:5173/api/agent/run
```

Invalid input fails before streaming with HTTP 422. After HTTP 200 begins,
infrastructure failures are terminal stream events rather than new HTTP statuses.

## Streaming Events

NDJSON (`application/x-ndjson`) sends one JSON event per newline:

`run_started`, `tool_started`, `tool_completed`, `tool_failed`, `answer`,
`error`, `run_completed`.

This is incremental execution-event streaming, not token-by-token answer streaming.
The frontend handles chunk-split lines, validates events, and renders text safely.
nginx disables buffering/caching and closes upstream when the client disconnects.
AbortController cancellation closes the request; shielded teardown closes MCP
resources. A new task starts with fresh state. Traces expose tool facts, not
chain-of-thought.

## Testing

Default backend tests (no live services), from `backend/`:

```shell
.venv/bin/python -m pytest
.venv/bin/python -m compileall -q app scripts alembic ../mcp_servers
```

Integration tests require a migrated, seeded PostgreSQL database; from `backend/`:

```shell
DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations \
  .venv/bin/python -m pytest -m integration
DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations \
  .venv/bin/alembic check
```

Frontend, from `frontend/`:

```shell
npm test
npm run typecheck
npm run lint
npm run build
```

Evaluations, from the repository root, require host Ollama for model cases and
the seeded DB for tool discovery/agent execution:

```shell
DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations \
  PYTHONPATH=.:backend backend/.venv/bin/python -m scripts.evaluate_tool_selection
PYTHONPATH=.:backend backend/.venv/bin/python -m scripts.evaluate_policy_retrieval
DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations \
  PYTHONPATH=.:backend backend/.venv/bin/python -m scripts.evaluate_agent
git diff --check
```

The full agent evaluation currently exits nonzero for the documented grounding
failure; do not suppress it or describe the suite as entirely passing.

## Security / Design Decisions

Narrow typed SELECT tools, strict discovered tool sets, duplicate-name rejection,
known-file-only policy access, and safe HTTP error messages reduce attack surface.
The harness is an execution boundary: model-proposed names must belong to discovered
tools, unknown names are rejected, and no `execute_sql` capability exists.
`max_steps` bounds model turns; tool failures become structured observations while
infrastructure failures terminate safely. This is not a complete security sandbox.
Agent/LLM layers never access the repository or domain files directly. API health
and maintenance scripts intentionally access the DB outside the agent path.
Backend Docker runs non-root; ports bind loopback and build contexts exclude local
secrets/dependencies/caches.

Model decisions and tool observations remain untrusted data, not authorization.
Read-only annotations alone do not enforce DB privileges: tools are read-only in
implementation, while example DB credentials are not a least-privilege role.
Prompt injection and factual correctness are not comprehensively solved.
See [architecture](docs/architecture.md).

## Trade-offs

Typed PostgreSQL tools preserve relational semantics; stdio MCP makes protocol
boundaries explicit without separate network services. A manual loop keeps
orchestration inspectable, lexical retrieval fits three small policies, and NDJSON
fits one request with server-to-client events. Host Ollama keeps local model/GPU
management separate from the app stack. See [interview notes](docs/interview-notes.md)
for concrete decision explanations and [CV bullets](docs/cv-bullets.md).

**Why a custom agent harness instead of LangGraph?** The execution loop was
implemented directly first to make discovery, routing, observations, stop conditions,
and failure semantics explicit and demonstrate the underlying runtime mechanics.
The current scope does not require a larger workflow state machine. LangGraph or
another workflow framework could become useful for persistence, resumable workflows,
complex branching, human approval, or larger state machines.

## Known Limitations

- qwen2.5:7b can confuse rank with product ID and choose the wrong ranked product.
- Lexical policy retrieval lacks semantic synonym handling.
- No authentication, authorization, rate limiting, or production TLS.
- No persistent conversations, retry/backoff, or distributed tracing.
- No backup/restore automation; Linux Docker path not fully verified.
- Ollama is host-managed; local inference is the dominant expected bottleneck.
- Synthetic data and small controlled fixtures; no production-scale load testing.
- Dependency ranges/base-image tags can drift; results are environment-specific.

These are deliberate scope boundaries or observed model limitations, not claims
of production readiness.

## Future Improvements

1. Compare stronger tool-calling models and expand grounding/factuality evaluations.
2. Add auth/tool authorization, rate limits, tracing, load tests, TLS, and backups
   before considering an internet-facing deployment.
3. Add retry/backoff and persistent run/conversation storage when requirements demand.
4. Consider hybrid policy search and model routing as corpus/traffic grows.
5. Require human approval and stronger privileges if write capabilities are introduced.
