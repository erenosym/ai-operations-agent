import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
from time import perf_counter

from app.agent import AgentRuntime, AgentRuntimeError, AgentStep
from app.llm import OllamaProvider
from app.mcp import OperationsMCPClient, PolicyMCPClient


@dataclass(frozen=True)
class AgentEvaluationCase:
    id: str
    prompt: str
    expected_tools_all: frozenset[str]
    expected_tools_any: frozenset[str]
    forbidden_tools: frozenset[str]
    required_answer_terms: tuple[str, ...]
    require_lookup_followup: bool
    require_top_product_followup: bool
    require_policy_source_term: bool


def load_cases() -> list[AgentEvaluationCase]:
    fixture_path = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/agent_cases.json"
    )
    raw_cases = json.loads(fixture_path.read_text())
    return [
        AgentEvaluationCase(
            id=case["id"],
            prompt=case["prompt"],
            expected_tools_all=frozenset(case["expected_tools_all"]),
            expected_tools_any=frozenset(case["expected_tools_any"]),
            forbidden_tools=frozenset(case["forbidden_tools"]),
            required_answer_terms=tuple(case["required_answer_terms"]),
            require_lookup_followup=case.get("require_lookup_followup", False),
            require_top_product_followup=case.get(
                "require_top_product_followup", False
            ),
            require_policy_source_term=case.get("require_policy_source_term", False),
        )
        for case in raw_cases
    ]


async def evaluate() -> int:
    cases = load_cases()
    completed = 0
    tool_checks_passed = 0
    answer_checks_passed = 0
    failures: list[str] = []
    started_at = perf_counter()

    async with OperationsMCPClient() as mcp_client, PolicyMCPClient() as policy_client:
        runtime = AgentRuntime(
            llm_provider=OllamaProvider(),
            mcp_client=mcp_client,
            policy_mcp_client=policy_client,
        )
        for case in cases:
            case_started_at = perf_counter()
            try:
                result = await runtime.run(case.prompt)
            except AgentRuntimeError as error:
                failures.append(f"- {case.id}: runtime failure: {error}")
                continue

            completed += 1
            successful_tools = {
                step.tool_name for step in result.steps if step.success
            }
            requested_tools = {step.tool_name for step in result.steps}
            required_all = case.expected_tools_all <= successful_tools
            required_any = (
                not case.expected_tools_any
                or bool(case.expected_tools_any & successful_tools)
            )
            forbidden_absent = not (case.forbidden_tools & successful_tools)
            dependent_followup = (
                _followup_targets_top_product(result.steps)
                if case.require_top_product_followup
                else True
            )
            lookup_followup = (
                _followup_targets_lookup_product(result.steps)
                if case.require_lookup_followup
                else True
            )
            tool_check = (
                required_all
                and required_any
                and forbidden_absent
                and dependent_followup
                and lookup_followup
            )
            if tool_check:
                tool_checks_passed += 1

            answer_lower = result.answer.lower()
            answer_check = all(
                term.lower() in answer_lower for term in case.required_answer_terms
            )
            if case.require_policy_source_term:
                answer_check = answer_check and _answer_uses_policy_observation(
                    result.steps, answer_lower
                )
            if answer_check:
                answer_checks_passed += 1

            elapsed_ms = (perf_counter() - case_started_at) * 1000
            print(
                f"[{case.id}] completed tools={sorted(successful_tools)!r} "
                f"requested={sorted(requested_tools)!r} duration_ms={elapsed_ms:.1f}"
            )
            if not tool_check or not answer_check:
                trace = [
                    f"{step.tool_name}({step.arguments!r})"
                    for step in result.steps
                ]
                failures.append(
                    f"- {case.id}: tool_check={tool_check}, "
                    f"answer_check={answer_check}, trace={trace!r}"
                )

    total_ms = (perf_counter() - started_at) * 1000
    print(f"Cases: {len(cases)}")
    print(f"Completed: {completed}")
    print(f"Expected tool behavior: {tool_checks_passed}/{len(cases)}")
    print(f"Answer checks passed: {answer_checks_passed}/{len(cases)}")
    print(f"Total duration ms: {total_ms:.1f}")
    if failures:
        print("Failures:")
        print("\n".join(failures))
    return 0 if not failures else 1


def _followup_targets_top_product(steps: tuple[AgentStep, ...]) -> bool:
    top_product_id: object = None
    for step in steps:
        if step.tool_name == "get_top_refunded_products":
            result = step.structured_result
            products = result.get("products") if isinstance(result, dict) else None
            if isinstance(products, list) and products and isinstance(products[0], dict):
                top_product_id = products[0].get("product_id")
        if (
            step.tool_name == "get_refund_reason_breakdown"
            and top_product_id is not None
        ):
            if step.arguments.get("product_id") == top_product_id:
                return True
    return False


def _followup_targets_lookup_product(steps: tuple[AgentStep, ...]) -> bool:
    lookup_product_id: object = None
    for step in steps:
        if step.tool_name == "find_products":
            result = step.structured_result
            products = result.get("products") if isinstance(result, dict) else None
            if isinstance(products, list) and products and isinstance(products[0], dict):
                lookup_product_id = products[0].get("product_id")
        if (
            step.tool_name == "get_refund_reason_breakdown"
            and lookup_product_id is not None
        ):
            if step.arguments.get("product_id") == lookup_product_id:
                return True
    return False


def _answer_uses_policy_observation(
    steps: tuple[AgentStep, ...], answer_lower: str
) -> bool:
    for step in steps:
        if step.tool_name != "search_policy" or not step.success:
            continue
        results = step.structured_result.get("results", [])
        if not isinstance(results, list):
            continue
        for result in results:
            if not isinstance(result, dict):
                continue
            section = result.get("section_title")
            source = result.get("source")
            if isinstance(section, str) and section.lower() in answer_lower:
                return True
            if isinstance(source, str):
                source_label = source.removesuffix(".md").replace("_", " ")
                if source_label in answer_lower:
                    return True
    return False


def main() -> None:
    raise SystemExit(asyncio.run(evaluate()))


if __name__ == "__main__":
    main()
