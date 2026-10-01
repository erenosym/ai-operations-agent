# Evaluation

Measured locally on 2026-10-01 using host Ollama qwen2.5:7b (temperature 0),
PostgreSQL 17 and the seeded synthetic dataset. Fixtures are controlled,
deterministic inputs; model/runtime versions and hardware can still change outputs.

| Evaluation | Cases | Result |
| --- | ---: | ---: |
| Tool selection | 16 | 16/16 |
| Policy retrieval | 8 | 8/8 |
| Agent completion | 13 | 13/13 |
| Agent answer checks | 13 | 13/13 |
| Agent tool behavior | 13 | 12/13 |

Results are from the project's deterministic local evaluation fixtures.

## Tool-selection evaluation

16 cases; 16/16 correct selection. The evaluator discovers MCP schemas and asks
qwen2.5:7b to select the expected capability for controlled prompts (including a
no-tool case). It checks selected names, not all argument values.

This does not prove correct arguments in all situations, multi-step grounding,
or correct final answers generally. A correct tool name can carry the wrong ID.

Fixture: backend/tests/fixtures/tool_selection_cases.json.
Runner: backend/scripts/evaluate_tool_selection.py.

## Policy retrieval evaluation

Eight cases; 8/8 top-1. Tests deterministic lexical policy retrieval against known
section/source expectations, without LLM inference.

This does not establish semantic quality for synonyms, unfamiliar phrasing,
adversarial documents, a larger corpus, or unseen policy questions.

Fixture: backend/tests/fixtures/policy_retrieval_cases.json.
Runner: backend/scripts/evaluate_policy_retrieval.py.

## Agent evaluation

13 cases: completion 13/13, answer checks 13/13, expected tool behavior 12/13.
The runtime successfully executes bounded orchestration, but the local model can
confuse ranked position with entity ID during a dependent follow-up.

The remaining failing case is multi_tool_analysis. In the measured host dataset,
the top product has ID 57; the model invokes get_refund_reason_breakdown with
product_id 1 instead. IDs are database identities and can differ on a fresh volume;
the invariant is to copy the returned top row's product_id, never its rank.

Completion means runtime.run returned without an AgentRuntimeError. Answer checks
require specified terms and, for selected policy cases, an observed source/section
reference. They are not exhaustive correctness judgments. Expected tool behavior
checks successful/forbidden tools and dependent lookup/top-product follow-up IDs
where configured. These checks can expose failures that answer-term checks miss.

The script intentionally returns exit code 1 when any case fails. Do not label this
as a fully passing agent suite or suppress that failure in reports.

Fixture: backend/tests/fixtures/agent_cases.json.
Runner: backend/scripts/evaluate_agent.py.

Tool-selection correctness != end-to-end agent correctness. Execution, argument
grounding, policy attribution and answer factuality need separate assessment.

## Grounding improvement story

Initially, named products could not reliably map to database IDs. A typed
find_products capability added bounded exact-name-first/name-category lookup.
Named-product grounding regression cases then passed without hardcoded IDs or
a runtime repair. Explicit rank metadata clarified ordered tool observations,
but one rank-as-ID dependent-reference failure remains in qwen2.5:7b.

The Docker combined-analysis smoke run also chose the wrong ranked product for
follow-up despite successfully exercising SQL, policies and streaming. That is
a semantic failure, not infrastructure success masquerading as correct analysis.

## Scope warning

All metrics apply only to these small controlled local sets and synthetic data.
They are not general model accuracy, production reliability, or user-impact metrics.
Temperature zero is not a cross-version reproducibility guarantee. Seed values
are repeatable, while generated identity IDs depend on database sequence history.

The earlier README claim that September 30 was mistakenly used as an exclusive
end date was incorrect: calendar end_date is inclusive; the repository converts
it to an exclusive timestamp at midnight the following day. The wrong-product
finding remains valid.

## Reproduce

From the repository root with migrated/seeded PostgreSQL and host Ollama running:

```shell
DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations \
  PYTHONPATH=.:backend backend/.venv/bin/python -m scripts.evaluate_tool_selection
PYTHONPATH=.:backend backend/.venv/bin/python -m scripts.evaluate_policy_retrieval
DATABASE_URL=postgresql+asyncpg://operations:operations@localhost:5432/operations \
  PYTHONPATH=.:backend backend/.venv/bin/python -m scripts.evaluate_agent
```

See [README testing](../README.md#testing) for installation and regression commands.

## Review and verification coverage

Final release-candidate checks on 2026-10-01: 84 default backend tests, four real
integration tests, and 14 frontend tests passed; frontend type-check/lint/build,
Python compilation, Alembic check and Compose config/build passed. The isolated
nginx → API smoke completed database and policy calls with healthy PostgreSQL.
Its wrong-product follow-up is a model failure, not a passing semantic analysis.

Default tests exercise tool schema preservation, strict allowlists, duplicate-name
rejection, ownership routing, model/provider errors, bounded turns, recovery,
event ordering, safe API errors, cancellation/partial-startup cleanup, repository
validation and seed invariants. Frontend tests cover split NDJSON, malformed/failed
streams, cancellation and state updates. Integration tests exercise real stdio
servers and seeded queries. Docker smoke verifies networking/build/runtime paths.
An oversized newline-terminated event previously bypassed the frontend's existing
partial-line size check; the final review extended that same limit to complete
events and added two regression cases. No model-grounding repair was added.

Gaps remain: no automated import-boundary/layering test, adversarial tool-output
suite, broad semantic answer grader, multi-user load/capacity test, or Linux Docker
runner. Existing checks are useful, but are not proof of production security.
