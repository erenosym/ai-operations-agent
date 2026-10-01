import asyncio

from app.llm import ChatMessage, OPERATIONS_SYSTEM_PROMPT, OllamaProvider
from app.mcp import OperationsMCPClient

CASES = (
    (
        "Show me the top 3 products by refund rate from 2026-09-01 through 2026-09-30.",
        "get_top_refunded_products",
    ),
    (
        "What are the refund statistics for product 1 between 2026-09-01 and 2026-09-30?",
        "get_product_statistics",
    ),
    (
        "What are the most common refund reasons during September 2026?",
        "get_refund_reason_breakdown",
    ),
    ("Hello, how are you?", None),
)


async def check_tool_selection() -> None:
    provider = OllamaProvider()
    async with OperationsMCPClient() as mcp_client:
        tools = await mcp_client.list_tools()
        await mcp_client.validate_expected_tools(strict=True)

    for prompt, expected_tool in CASES:
        response = await provider.chat(
            [
                ChatMessage(role="system", content=OPERATIONS_SYSTEM_PROMPT),
                ChatMessage(role="user", content=prompt),
            ],
            tools,
        )
        predicted = response.tool_calls[0].name if len(response.tool_calls) == 1 else None
        print(f"expected={expected_tool!r} predicted={predicted!r} prompt={prompt!r}")
        expected_call_count = 0 if expected_tool is None else 1
        if predicted != expected_tool or len(response.tool_calls) != expected_call_count:
            raise RuntimeError("Ollama tool-selection smoke check failed")


def main() -> None:
    asyncio.run(check_tool_selection())


if __name__ == "__main__":
    main()
