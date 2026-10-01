# Interview notes

## Problem and architecture

**What problem does this solve?**

It helps investigate e-commerce operational facts and compare them with policy
rules in one local workflow, while exposing the tool evidence for review.

**What is the architecture?**

React → FastAPI (via nginx in Compose) → bounded AgentRuntime → Ollama and MCP
clients. Operations MCP delegates to PostgreSQL repositories; policy MCP delegates
to known-file lexical retrieval. Both servers are API-container subprocesses.

**Why PostgreSQL?**

Orders, products and refunds have relational integrity and aggregation needs.
SQL joins, constraints, exact NUMERIC money and predictable indexes fit those facts.

**Why async SQLAlchemy?**

Typed query/model boundaries and asyncpg integrate with the async API/MCP path.
Async I/O avoids blocking a request task, but does not increase model throughput
or remove database capacity limits.

**Why Alembic?**

Versioned, reviewable schema changes keep lifecycle separate from API requests.
Migrations are explicit; startup does not create tables or reset data.

**Why not put everything in a vector DB?**

Similarity search is not a replacement for transactional relationships, exact
refund arithmetic or constraints. Policy retrieval can evolve independently.

## MCP and tools

**Why MCP?**

It makes capability discovery and invocation an explicit reusable protocol
boundary, with schemas owned by servers instead of the model adapter.

**MCP vs REST?**

REST serves this browser application. MCP supplies discoverable capabilities to
the agent. They solve different integration problems and coexist here.

**MCP vs tool calling?**

Tool calling is the model's structured selection of a name and arguments.
MCP discovers the capability and executes it through a client/server protocol.

**MCP vs agent?**

The server publishes, the client invokes, and the agent orchestrates observations
and next actions. MCP itself does not reason or select tools.

**Why no execute_sql?**

Arbitrary SQL makes the model responsible for schema interpretation, query safety
and unconstrained data access. Narrow tools bound those responsibilities.

**How do typed tools improve safety?**

They constrain inputs, date/limit validation and result shape while centralizing
query implementation. Types are not authorization or a guarantee of correct IDs.

**Why stdio MCP?**

Private pipes avoid new network services/auth configuration for a local project.
The official SDK handles protocol transport; diagnostics stay on stderr.

**How do multiple MCP servers work?**

Discover and strictly validate each server, merge schemas, then route names through
a dynamic owner map. The agent does not hardcode one server per tool call.

**How are tool-name collisions handled?**

Duplicate discovered names fail before model inference, so routing is never
silently ambiguous.

**Why API-container subprocesses instead of separate services?**

It preserves the existing stdio design with a small Compose stack and reproducible
module paths. Startup/pool overhead per run is a scaling trade-off.

## Orchestration and errors

**How does the manual agent loop work?**

Ask the provider with discovered schemas; execute allowed calls sequentially;
append results/errors as tool observations; repeat until an answer or step limit.

**Why a custom loop?**

The small bounded flow is inspectable and directly testable, with clear provider,
MCP and HTTP boundaries. It avoids framework complexity for the current scope.

**Why not LangGraph initially?**

No durable graph, human approval checkpoints or branching workflow is required.
Reconsider it if orchestration state becomes complex; this is not a claim that
frameworks are intrinsically worse.

**How do you prevent infinite loops?**

Cap model turns (default five, API maximum ten). This is not a global wall-clock
deadline or a strict total-tool-call limit.

**How are tool failures handled?**

Return a structured error observation so the model may correct its next action
within the remaining turn budget. Public tool-error messages are sanitized.

**How are infrastructure failures handled?**

Normalize MCP/provider errors into terminal agent errors; HTTP sends safe generic
error events. Shielded cleanup closes clients even during cancellation/startup failure.

## Retrieval and local inference

**Why lexical policy retrieval?**

Three small known documents allow deterministic, understandable section matching,
stable ranking and clear source attribution with minimal infrastructure.

**Why no embeddings or Qdrant?**

There is no demonstrated corpus-scale/semantic retrieval need. Add semantic or
hybrid retrieval only after measuring lexical failures on representative questions.

**Why local Ollama?**

It enables local development without a cloud API dependency and keeps model
serving behind one provider boundary. This does not constitute privacy compliance.

**Why qwen2.5:7b?**

It is the available local tool-calling baseline measured in this project. Its
remaining grounding failure is evidence to compare stronger models, not a hidden
claim of general reliability or optimal model choice.

**Why host Ollama?**

It keeps existing model storage/GPU setup separate from app containers; Compose
connects to it through host.docker.internal. Model lifecycle remains a prerequisite.

## HTTP, Docker and reproducibility

**Why NDJSON?**

One POST can incrementally deliver structured execution events with ordinary fetch.
Each newline is an event; the browser handles arbitrary chunk boundaries.

**Why not WebSockets?**

The task needs one-way run events, not a durable bidirectional channel. WebSockets
would add lifecycle complexity without a current requirement.

**How does nginx preserve streaming?**

Disable proxy buffering, request buffering, cache and proxy gzip; use suitable
idle timeouts and close upstream on client disconnect. Real tool events arrived
before the final answer in the Compose smoke check.

**How does Docker networking work?**

Browser → published frontend → nginx /api proxy → api:8001. API reaches
postgres:5432 and host.docker.internal:11434; MCP remains local stdio.

**Why postgres:5432?**

Compose DNS resolves the database service. localhost inside API means API itself,
not the PostgreSQL container. Host development uses the published localhost port.

**Why host.docker.internal?**

It reaches host Ollama from Docker Desktop. Linux host-gateway mapping exists,
but host listener/firewall behavior remains unverified.

**How are database migrations managed?**

Run compose run --rm api alembic upgrade head explicitly; alembic check detects
model/migration drift. Seeding is separate and never automatic.

**How is seed data reproducible?**

Random seed 20261001 and reference date 2026-10-01 yield 500 customers, 50 products,
2,000 orders, 5,877 items and 404 refunds. Named patterns are fixed; identity
sequences can produce different IDs after reset. Use lookup, not hardcoded IDs.

**Are builds reproducible?**

Frontend npm ci uses a lockfile. Backend version ranges and Docker tags are not
fully locked, so builds and model results are not bit-identical across environments.

## Evaluation and failure

**What did evaluation reveal?**

16/16 tool selection and 8/8 lexical retrieval, but only 12/13 agent tool checks,
despite 13/13 completion and answer-term checks. Each layer measures something different.

**What failed during development?**

Named products initially lacked reliable name-to-ID grounding; dependent follow-ups
also confused ranked position with entity ID. End-to-end checks exposed both.

**How did find_products improve grounding?**

It gave the model a typed exact-name-first lookup and explicit returned IDs.
Named-product regression cases now pass without runtime ID substitution.

**What failure still remains?**

In multi_tool_analysis, qwen2.5:7b passes rank 1 as product_id instead of the top
row's actual ID. A Docker smoke run also followed up on the wrong ranked product.

**Why is tool-selection accuracy not enough?**

The right capability with a wrong identifier still yields the wrong investigation.
Answer-term checks can pass despite that semantic error.

## Failure story

1. Initial controlled tool-selection evaluation looked excellent.
2. End-to-end agent testing exposed product-ID grounding failures.
3. The first grounding fix was not a bigger prompt or hardcoded IDs.
4. A typed find_products lookup capability was added.
5. Named-product grounding improved and regression cases passed.
6. Structured rank metadata clarified dependent observations.
7. One qwen2.5:7b rank-as-ID failure still remains; no runtime repair hides it.
8. Lesson: selection, execution, grounding and answer quality need separate tests.

The current prompt also instructs the model not to confuse rank with IDs, but
instructions and clearer observations alone have not eliminated the failure.
Report the limitation alongside successes, not as an afterthought.

## Production and scale

**What would you change for production?**

Auth/tool authorization, least-privilege DB roles, TLS, rate/concurrency limits,
backups, tracing, load tests, dependency locking and broader adversarial/factuality
evaluations before exposing it publicly.

**What happens at 100x traffic?**

We have not measured that. Benchmark concurrent runs first; local inference,
per-run subprocess startup and DB pools are likely pressure points. Introduce
admission control before assuming more API replicas solve capacity.

**Where are the current bottlenecks?**

Local model latency is the dominant expected bottleneck; model turns multiply it.
Subprocess discovery and database pools add overhead. Small-dataset SQL plans
are documented, but do not predict production-scale behavior.

**What would you monitor in production?**

Run latency/errors/cancellations, model turn counts, tool success and grounding,
Ollama utilization, active/orphan subprocesses, DB pool/query latency, stream
disconnects and retrieval/factuality regressions—without logging secrets/reasoning.

**What comes next?**

Compare models and expand evaluations; add deployment safety and capacity controls;
then consider persistence/retries and hybrid retrieval if actual requirements grow.
Write tools would require explicit authorization and human approval boundaries.
