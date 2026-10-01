# AI Operations Agent

## Project goal

Build an AI operations agent that helps an e-commerce company analyze structured operational data and apply internal policy documents safely through narrow, typed tools.

## Quick start: full Compose stack

Prerequisites: Docker Compose and Ollama running on the host with `qwen2.5:7b`
already installed (`ollama list` checks this). Compose does not start Ollama or pull
models. Copy `.env.example` to `.env` and review the local development credentials.
Run these commands from the repository root:

```shell
docker compose up --build -d
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m scripts.seed_database
docker compose ps
```

Open **http://localhost:5173**. API health is at **http://localhost:8001/health**
or **http://localhost:5173/api/health**. On an existing seeded database, skip seeding;
the seed command intentionally refuses to overwrite existing rows. Migrations are
explicit, so apply them before submitting agent tasks on first launch. Health checks
verify database connectivity, not migration/seed completion or Ollama availability.

```mermaid
flowchart LR
    browser[Browser] --> frontend["frontend: nginx / React"]
    frontend -->|"/api/ — unbuffered"| api["api: FastAPI / AgentRuntime"]
    api --> ollama["Host Ollama: qwen2.5:7b"]
    api --> clients["MCP clients inside api"]
    clients -->|stdio| operations["operations-postgres subprocess"]
    clients -->|stdio| policy["operations-policy subprocess"]
    operations --> postgres["postgres: PostgreSQL / named volume"]
    policy --> files["Markdown policies inside api image"]
```

The API uses a non-root Python 3.13 slim runtime with `/app/backend`,
`/app/mcp_servers`, and `/app/policies`. Both MCP servers are per-run Python
subprocesses inside that container; there are no separate MCP services. The frontend
uses a Node build stage and nginx to serve production assets. It embeds the relative
API base `/api`, never a Docker hostname or host-specific API URL. nginx strips the
`/api/` prefix and proxies to `api:8001`, with response/request buffering and caching
disabled. Its 300-second idle timeout accommodates local inference; client disconnects
close upstream requests so FastAPI can cancel the run and clean up MCP processes.

### Compose configuration

| Variable | Default / purpose |
| --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | `operations`; local development defaults |
| `DATABASE_URL` | Compose connection using `postgres:5432`; keep credentials and database synchronized with `POSTGRES_*` |
| `DOCKER_OLLAMA_BASE_URL` | `http://host.docker.internal:11434`, passed as `OLLAMA_BASE_URL` inside api |
| `OLLAMA_BASE_URL` | Host development default `http://localhost:11434`; not used as the Compose override |
| `OLLAMA_MODEL` | `qwen2.5:7b` |
| `FRONTEND_ORIGIN` | `http://localhost:5173`; host Vite CORS origin |
| `FRONTEND_PORT`, `API_PORT`, `POSTGRES_PORT` | Host loopback ports `5173`, `8001`, `5432` |

Container ports remain 80, 8001, and 5432. Stop host Vite/Uvicorn processes before
using the same published ports, or override the host port variables. Inside Compose,
PostgreSQL must use `postgres`, never `localhost`. Passwords containing URI-reserved
characters must be URL-encoded in `DATABASE_URL`. Do not use these example credentials
for a publicly exposed deployment.

Docker Desktop provides host connectivity on macOS. A `host-gateway` mapping is also
included for Linux. On Linux, a host Ollama service bound only to loopback may not
accept container connections; configure its listening address and host firewall to
allow the Docker network deliberately. Do not expose Ollama publicly. No host bind
mounts are needed, and local `.env`, Git metadata, virtual environments, dependencies,
and caches are excluded from image builds.

### Database lifecycle and useful commands

```shell
docker compose logs --tail=100 api frontend postgres
docker compose exec api python -m scripts.check_mcp_client
docker compose exec api python -m scripts.check_policy_mcp_client
docker compose exec api alembic check
docker compose down
docker compose up -d
```

`down` preserves the existing `postgres_data` named volume. **`docker compose down -v`
deletes the database volume and all its data**; use it only for disposable environments.
Migrations and seeding never run automatically. For an intentional development-data
reset, use `docker compose run --rm api python -m scripts.seed_database --reset`.
This replaces application rows; it is not a normal startup step.

Services use `unless-stopped`. API startup waits for PostgreSQL health; frontend
startup waits for API database health. API health does not launch MCP processes.
Standard container stdout/stderr carries Uvicorn, nginx, and PostgreSQL diagnostics;
MCP protocol stdout stays on the client's private subprocess pipe.

To test an isolated fresh database without touching the normal project, use a unique
project name and ports consistently for every command, for example:

```shell
POSTGRES_PORT=15432 API_PORT=18001 FRONTEND_PORT=15173 \
  docker compose -p operations-compose-check up --build -d
POSTGRES_PORT=15432 API_PORT=18001 FRONTEND_PORT=15173 \
  docker compose -p operations-compose-check run --rm api alembic upgrade head
POSTGRES_PORT=15432 API_PORT=18001 FRONTEND_PORT=15173 \
  docker compose -p operations-compose-check run --rm api python -m scripts.seed_database
```

This is a local production-style stack, not an internet deployment: authentication,
TLS, backups, and resource limits are not configured. The measured small-model
dependent-ID grounding limitation remains; containerization does not change agent
behavior. The Docker combined-analysis smoke run also selected the wrong ranked
product for follow-up and used September 30 as the exclusive end date. Tool execution
and streaming succeeded, but model-generated analysis still requires review.
Host development remains supported below, using only the PostgreSQL service
in Docker and running Vite, FastAPI, and Ollama on the host.

## Business use case

The system is intended to answer operational questions that combine e-commerce records—such as customers, products, orders, order items, and refunds—with refund, return, and shipping policies. A representative task is analyzing recent refunds, ranking products by refund rate, identifying common reasons, retrieving the applicable policy, and summarizing the findings.

## High-level architecture

- PostgreSQL with relational e-commerce data modeling
- Async SQLAlchemy and Alembic migrations
- Narrow, typed operational tools exposed through MCP servers
- A small tool-calling agent runtime built without LangChain or LangGraph initially
- FastAPI backend and React frontend
- Docker Compose for local services
- Observable tool execution, automated tests, and evaluations

The agent will not receive an unrestricted arbitrary SQL execution tool.

## Current status

The repository now contains the database-aware FastAPI health endpoint, asynchronous PostgreSQL layer, schema and seed data, typed business queries, independent read-only PostgreSQL and policy MCP servers, their application clients, an Ollama boundary, and a bounded multi-server agent runtime exposed through a streamed HTTP endpoint. A React operations workspace consumes that stream. Persistent conversations are not implemented.

## Relational schema

The initial SQLAlchemy ORM schema contains `customers`, `products`, `orders`, `order_items`, and `refunds`. Models live in `backend/app/models/`, while Alembic migrations—not FastAPI startup—own the PostgreSQL schema.

Run migrations from `backend/` with an appropriate host-accessible `DATABASE_URL`:

```shell
alembic upgrade head
alembic downgrade base
alembic current
```

## Development seed data

The development dataset uses random seed `20261001` and fixed reference date `2026-10-01`. It generates 500 synthetic customers, 50 products, 2,000 orders, roughly 5,900 order items, and roughly 400 refunds, including documented high-, elevated-, and low-refund product patterns.

After migrating the database, seed it from `backend/` using the host-side database URL:

```shell
DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations .venv/bin/python -m scripts.seed_database
```

The normal command refuses to run when application tables contain rows. To explicitly replace local development data, add `--reset`; this deletes application rows in dependency-safe order but does not drop or downgrade the schema.

## Business query layer

The backend currently exposes these internal, typed Python operations:

- `find_products`
- `get_customer_orders`
- `get_recent_refunds`
- `get_top_refunded_products`
- `get_product_statistics`
- `get_refund_reason_breakdown`

These functions return purpose-specific dataclasses and have no dedicated HTTP endpoints; `/agent/run` can invoke them through MCP. The MCP server delegates to them without duplicating SQL. Analytics use inclusive-start/exclusive-end UTC date boundaries. Product `refund_rate` is a ratio in `[0,1]`: distinct refunded order items divided by sold order items for non-cancelled orders in the selected order-date cohort, with refunds also requested during that interval. Multiple refund records for one item therefore do not inflate the rate.

Named product resolution uses the typed, read-only `find_products` capability rather than allowing the model to guess database identifiers. It provides exact-name-first matching plus bounded name/category substring matching; it is not a general entity-resolution system.

## Operations PostgreSQL MCP server

The `operations-postgres` server exposes the six business operations above as read-only MCP tools over stdio. The application boundary is:

```text
Application
  → OperationsMCPClient
  → stdio MCP
  → operations-postgres MCP server
  → repository/query layer
  → PostgreSQL
```

Arbitrary SQL is intentionally not exposed. `OperationsMCPClient` discovers and invokes the server's six capabilities without importing repositories, ORM models, or database sessions. Successful calls require structured object results; MCP tool errors raise `MCPToolCallError` instead of being presented as successes. The SDK keeps server stderr separate from the stdout protocol stream, so diagnostics remain visible without corrupting MCP messages. See `mcp_servers/postgres_server/README.md` for local server and Inspector commands.

The architectural roles are distinct:

- A repository function is the application/business data-access boundary.
- An MCP tool is a protocol-visible capability exposed to an MCP client.
- An MCP server publishes and supports discovery of those capabilities.
- The MCP client connects to the server, discovers capabilities, and invokes them.
- The agent decides when to invoke those capabilities; neither a server nor a client is the agent.

## Operational policy lookup

Three concise synthetic documents in `policies/` define refund, return, and shipping
rules. The independent `operations-policy` MCP server loads only those known files,
splits them at level-two Markdown headings, and exposes one read-only tool:
`search_policy`. Callers provide a query, optional `refund`, `return`, or `shipping`
filter, and a bounded limit; they cannot provide filesystem paths.

Retrieval is deterministic lexical matching, not vector RAG. An exact normalized
query in a heading adds 100 points, an exact query in section text adds 50, each
query token shared with a heading adds 10, and each token shared with the body adds
1. Results sort by descending score and then stable policy/section/source keys.
Structured results retain the policy type and name, section title, content, score,
and source filename so the model can attribute a rule. No embeddings, Qdrant,
reranker, external search API, or arbitrary filesystem tool is involved.

`PolicyMCPClient` launches the server over stdio, validates that its sole capability
is `search_policy`, and returns structured protocol results. It contains no parsing
or file-reading logic.

For a host-side client smoke check with the seeded database running:

```shell
DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations \
  PYTHONPATH=.:backend backend/.venv/bin/python -m scripts.check_mcp_client
```

## Manual agent runtime

The LLM boundary uses the official asynchronous Ollama Python client. `AgentRuntime` implements the framework-independent orchestration loop:

```mermaid
flowchart LR
    user["User"] --> agent["AgentRuntime"]
    agent --> llm["Ollama / qwen2.5:7b"]
    llm --> agent
    agent --> operations["OperationsMCPClient"]
    operations --> postgres["operations-postgres / stdio"]
    postgres --> repo["Repository layer"]
    repo --> db["PostgreSQL facts"]
    agent --> policy_client["PolicyMCPClient"]
    policy_client --> policy_server["operations-policy / stdio"]
    policy_server --> policies["Synthetic Markdown rules"]
    operations --> agent
    policy_client --> agent
```

The runtime discovers tool schemas from both MCP servers once per run, validates each
allowlist, and builds a discovered `tool name → owning client` map. Duplicate tool
names fail discovery clearly instead of selecting a server silently. It asks the
model what to do, routes requested tools through that ownership map, appends
structured observations, and continues until the model returns a non-empty answer.
This lets one answer combine structured PostgreSQL facts with Markdown policy rules
without putting database or filesystem access in `AgentRuntime`.

`AgentResult` contains only the final answer and observable tool facts: names, arguments, success, MCP-call duration, safe error details, and structured results. Hidden reasoning is neither stored nor logged. Unknown tools—including `execute_sql`—are rejected by the discovery allowlist and never reach MCP. When a named product must be passed to an ID-based tool, the model can resolve it through `find_products`. Parallel execution, retries, and persistent conversation history remain intentionally deferred.

Agent orchestration, LLM tool selection, MCP capability discovery/execution, and repository data access remain separate boundaries. Tool schemas originate from MCP and are not duplicated in the agent or LLM layers; neither layer imports repositories or database models.

Local development defaults to `OLLAMA_BASE_URL=http://localhost:11434` and the already tool-capable `OLLAMA_MODEL=qwen2.5:7b`. Ollama and that model must be available locally. Override either setting through the environment; no cloud API key is used.

Run the real agent smoke scenarios, policy retrieval evaluation, expanded agent
evaluation, or expanded selection evaluation from the repository root:

```shell
DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations \
  PYTHONPATH=.:backend backend/.venv/bin/python -m scripts.check_agent
DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations \
  PYTHONPATH=.:backend backend/.venv/bin/python -m scripts.evaluate_agent
DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations \
  PYTHONPATH=.:backend backend/.venv/bin/python -m scripts.evaluate_tool_selection
PYTHONPATH=.:backend backend/.venv/bin/python -m scripts.evaluate_policy_retrieval
PYTHONPATH=.:backend backend/.venv/bin/python -m scripts.check_policy_mcp_client
```

Both MCP servers use stdio. FastAPI exposes the runtime through `POST /agent/run`.

## Streamed agent API

The architecture is Client → FastAPI `/agent/run` → AgentRuntime → Ollama and
the two MCP clients → stdio MCP servers → PostgreSQL / Markdown policies.
The React frontend consumes this endpoint; persistent conversation history is not implemented.

Start the backend from `backend/`:

```shell
DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations \
  PYTHONPATH=.:.. .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```shell
curl -N http://127.0.0.1:8000/agent/run \
  -H 'Content-Type: application/json' \
  -d '{"message":"What is the policy for a damaged item?","max_steps":5}'
```

The request accepts a trimmed, nonempty `message` of at most 10,000 characters
and optional integer `max_steps` from 1–10 (default 5). Other fields are rejected.
Validation errors return HTTP 422 before streaming. Valid requests return HTTP 200
with `application/x-ndjson`: every physical line is an independently parseable JSON
object. HTTP success means the stream was established; execution success or failure
is represented inside the stream. A late failure cannot change the HTTP status.

| Event | Fields in addition to `type` |
| --- | --- |
| `run_started` | none |
| `tool_started` | `step`, `tool_name`, `arguments` |
| `tool_completed` | `step`, `tool_name`, `duration_ms`, `result` |
| `tool_failed` | `step`, `tool_name`, `duration_ms`, safe `message` |
| `answer` | `content` |
| `run_completed` | `tool_calls_count`, `termination_reason` |
| `error` | `code`, safe `message` |

Successful ordering is `run_started`, zero or more tool start/completion pairs,
`answer`, then `run_completed`. A recoverable tool failure emits `tool_failed` and
the model may continue. Terminal failures emit a single `error` instead of successful
completion. Codes distinguish infrastructure, maximum-step, and response failures.
Startup failure may emit `error` before runtime discovery begins. A connection failure
during an invocation may leave a `tool_started` followed by terminal `error`.

Structured bounded tool results are included, preserving money/ratio strings and
policy source metadata. Provider diagnostics and hidden model reasoning are absent.
Public tool failure messages are deliberately generic; runtime recovery still sees
the original tool validation detail.

`run_stream()` owns the orchestration loop. Existing `run()` callers consume the same
events to construct `AgentResult`, retaining existing exception behavior. Each HTTP
request creates its own MCP clients; contexts close on success, failure, partial
startup, and client cancellation. Cancellation ends execution without background
continuation. Cleanup is shielded from the request's cancellation scope. Health checks
remain database-aware and do not launch MCP subprocesses.

The incremental smoke client is available as:

```shell
PYTHONPATH=.:.. .venv/bin/python -m scripts.check_agent_api --message 'Hello.'
```

## Development infrastructure

### React operations workspace

The frontend uses React, TypeScript, Vite, plain hooks, and CSS. Its only application
API is FastAPI. It never contacts Ollama, MCP servers, PostgreSQL, or policy files.

```text
Browser / React → FastAPI /agent/run → AgentRuntime → Ollama
                                       └→ MCP clients
                                           ├→ operations-postgres → PostgreSQL
                                           └→ operations-policy → policy Markdown
```

With the existing seeded PostgreSQL database and local Ollama `qwen2.5:7b` available,
start development from the repository root in separate terminals:

```shell
docker compose up -d postgres
```

```shell
cd backend
DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations \
  FRONTEND_ORIGIN=http://localhost:5173 PYTHONPATH=.:.. \
  .venv/bin/uvicorn app.main:app --host localhost --port 8001
```

```shell
cd frontend
npm install
npm run dev
```

The UI defaults to `http://localhost:8001`. Set `VITE_API_BASE_URL` in
`frontend/.env` to override it; `frontend/.env.example` shows the format. Vite exposes
these values to browsers, so they must contain no secrets. Backend `FRONTEND_ORIGIN`
permits one exact origin (default `http://localhost:5173`) for development CORS.

Fetch consumes NDJSON incrementally, buffering partial lines and validating each
event. The trace displays real tool events, expandable JSON, original product
ordering, and policy source metadata. Answers render as safe plain text. Stop aborts
the request and displays a neutral cancelled state; a new task clears the prior
result. Nothing is persisted. Server error events, HTTP failures, malformed streams,
and network interruption are presented separately from user cancellation.

Frontend verification, from `frontend/`:

```shell
npm test
npm run typecheck
npm run lint
npm run build
```

PostgreSQL runs in Docker Compose with data stored in a named volume. Copy `.env.example` to `.env`, then manage the service from the repository root:

```shell
docker compose up -d postgres
docker compose ps
docker compose down
```

`docker compose down` removes the container and network but preserves the database volume. `docker compose down -v` also permanently removes the local database volume and its data.

The API container connects to PostgreSQL at `postgres:5432`. Host-side tools normally connect through the published port at `localhost:5432`.

When running the backend directly on the host, override only the hostname for that process, for example with `DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations`. Keep the Compose-oriented default on `postgres:5432` for the API container.

## Completed major milestones

1. Define the relational schema, PostgreSQL environment, and migrations.
2. Add deterministic seed data and database integration tests.
3. Implement narrow typed tools and MCP servers for data, policies, and analytics.
4. Build the minimal agent runtime and observable tool execution.
5. Add the FastAPI application workflows and React interface.
6. Package local services with Docker Compose.
7. Expand automated tests and add an evaluation harness.
