import asyncio

import pytest

from app.mcp import EXPECTED_POLICY_TOOLS, MCPToolCallError, PolicyMCPClient

pytestmark = pytest.mark.integration


async def _exercise_policy_server() -> None:
    async with PolicyMCPClient() as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == EXPECTED_POLICY_TOOLS
        await client.validate_expected_tools(strict=True, tools=tools)
        for query, section in (
            ("defective item refund", "Defective or Damaged Items"),
            ("size issue return", "Size-Related Returns"),
            ("lost shipment", "Lost or Damaged Shipments"),
            ("refund processing time", "Refund Processing"),
        ):
            result = await client.search_policy(query)
            assert result["results"][0]["section_title"] == section
        with pytest.raises(MCPToolCallError, match="policy_type"):
            await client.search_policy("refund", policy_type="unknown")


def test_policy_client_and_real_stdio_server() -> None:
    asyncio.run(_exercise_policy_server())
