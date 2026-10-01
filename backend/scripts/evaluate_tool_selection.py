import asyncio
from dataclasses import dataclass
import json
from pathlib import Path

from app.llm import ChatMessage, OPERATIONS_SYSTEM_PROMPT, OllamaProvider
from app.mcp import OperationsMCPClient, PolicyMCPClient


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    prompt: str
    expected_tool: str | None
    expected_argument_keys: frozenset[str]


def load_cases() -> list[EvaluationCase]:
    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/tool_selection_cases.json"
    )
    raw_cases = json.loads(fixture_path.read_text())
    return [
        EvaluationCase(
            id=case["id"],
            prompt=case["prompt"],
            expected_tool=case["expected_tool"],
            expected_argument_keys=frozenset(case["expected_argument_keys"]),
        )
        for case in raw_cases
    ]


async def evaluate() -> int:
    cases = load_cases()
    provider = OllamaProvider()
    async with OperationsMCPClient() as mcp_client, PolicyMCPClient() as policy_client:
        operations_tools = await mcp_client.list_tools()
        policy_tools = await policy_client.list_tools()
        await mcp_client.validate_expected_tools(strict=True, tools=operations_tools)
        await policy_client.validate_expected_tools(strict=True, tools=policy_tools)
        tools = operations_tools + policy_tools

    correct = 0
    failures: list[str] = []
    for case in cases:
        response = await provider.chat(
            [
                ChatMessage(role="system", content=OPERATIONS_SYSTEM_PROMPT),
                ChatMessage(role="user", content=case.prompt),
            ],
            tools,
        )
        calls = response.tool_calls
        predicted = calls[0].name if len(calls) == 1 else None
        argument_keys = frozenset(calls[0].arguments) if len(calls) == 1 else frozenset()
        passed = (
            predicted == case.expected_tool
            and (case.expected_tool is None or case.expected_argument_keys <= argument_keys)
            and len(calls) <= 1
        )
        if passed:
            correct += 1
        else:
            failures.append(
                f"- {case.id}: expected={case.expected_tool!r}, "
                f"predicted={[call.name for call in calls]!r}, "
                f"argument_keys={sorted(argument_keys)!r}"
            )

    print(f"Cases: {len(cases)}")
    print(f"Correct tool selection: {correct}")
    print(f"Accuracy: {correct / len(cases):.2f}")
    if failures:
        print("Failures:")
        print("\n".join(failures))
    return 0 if not failures else 1


def main() -> None:
    raise SystemExit(asyncio.run(evaluate()))


if __name__ == "__main__":
    main()
