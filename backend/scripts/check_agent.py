import asyncio

from app.agent import AgentRuntime
from app.llm import OllamaProvider
from app.mcp import OperationsMCPClient, PolicyMCPClient

SCENARIOS = (
    (
        "top-products",
        "Analyze the top 3 products by refund rate during September 2026 and summarize the result.",
        {"get_top_refunded_products"},
    ),
    (
        "shoe-reasons",
        "Why were StridePro Running Shoes being refunded during September 2026?",
        {"find_products", "get_refund_reason_breakdown"},
    ),
    (
        "recent-refunds",
        "Show the recent refunds from September 20 through September 30, 2026 and summarize what stands out.",
        {"get_recent_refunds"},
    ),
    ("greeting", "Hello.", set()),
    (
        "multi-tool",
        "Analyze the top 3 products by refund rate in September 2026, then explain "
        "the main refund reasons for the worst-performing product.",
        {"get_top_refunded_products", "get_refund_reason_breakdown"},
    ),
    (
        "policy",
        "What is the policy for a customer who receives a damaged item?",
        {"search_policy"},
    ),
)


async def check_agent() -> None:
    provider = OllamaProvider()
    async with OperationsMCPClient() as mcp_client, PolicyMCPClient() as policy_client:
        runtime = AgentRuntime(
            llm_provider=provider,
            mcp_client=mcp_client,
            policy_mcp_client=policy_client,
        )
        for case_id, prompt, required_tools in SCENARIOS:
            result = await runtime.run(prompt)
            successful_tools = {
                step.tool_name for step in result.steps if step.success
            }
            print(f"[{case_id}] tools={[step.tool_name for step in result.steps]}")
            for step in result.steps:
                print(
                    f"  step={step.step_number} tool={step.tool_name} "
                    f"arguments={step.arguments!r} success={step.success} "
                    f"duration_ms={step.duration_ms}"
                )
            print(f"  answer={result.answer}")
            if not required_tools <= successful_tools:
                raise RuntimeError(
                    f"Scenario {case_id} did not use required tools: "
                    f"{sorted(required_tools - successful_tools)}"
                )


def main() -> None:
    asyncio.run(check_agent())


if __name__ == "__main__":
    main()
