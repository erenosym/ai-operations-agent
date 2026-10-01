import asyncio
from types import SimpleNamespace

import pytest

from app.mcp import EXPECTED_POLICY_TOOLS, MCPToolValidationError, PolicyMCPClient


class StubSDKClient:
    def __init__(self, tools: list[object], result: object | None = None) -> None:
        self.tools = tools
        self.result = result
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def list_tools(self) -> object:
        return SimpleNamespace(tools=self.tools)

    async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        self.calls.append((name, arguments))
        return self.result


def _tool(name: str) -> object:
    return SimpleNamespace(
        name=name,
        description="policy search",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )


def test_policy_client_discovers_validates_and_wraps_calls() -> None:
    async def run() -> None:
        client = PolicyMCPClient()
        sdk = StubSDKClient(
            [_tool("search_policy")],
            SimpleNamespace(
                is_error=False,
                structured_content={"results": [{"source": "refund_policy.md"}]},
                content=[],
            ),
        )
        client._sdk_client = sdk  # type: ignore[assignment]
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == EXPECTED_POLICY_TOOLS
        await client.validate_expected_tools(strict=True, tools=tools)
        result = await client.search_policy("damaged", policy_type="refund", limit=2)
        assert result["results"][0]["source"] == "refund_policy.md"
        assert sdk.calls == [
            (
                "search_policy",
                {"query": "damaged", "limit": 2, "policy_type": "refund"},
            )
        ]

        client._sdk_client = StubSDKClient([_tool("read_file")])  # type: ignore[assignment]
        with pytest.raises(MCPToolValidationError):
            await client.validate_expected_tools(strict=True)

    asyncio.run(run())
