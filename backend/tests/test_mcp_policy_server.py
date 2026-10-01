import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mcp_servers.policy_server import server


def test_only_search_policy_is_registered_with_structured_output() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    assert [tool.name for tool in tools] == ["search_policy"]
    tool = tools[0]
    assert tool.description == (
        "Search operational refund, return, and shipping policy sections."
    )
    assert tool.input_schema["required"] == ["query"]
    assert tool.input_schema["properties"]["limit"]["default"] == 5
    assert tool.output_schema is not None
    assert tool.annotations.read_only_hint is True


def test_tool_returns_json_compatible_results_with_source() -> None:
    result = asyncio.run(
        server.mcp.call_tool(
            "search_policy", {"query": "lost shipment", "policy_type": "shipping"}
        )
    )
    assert result.structured_content is not None
    match = result.structured_content["results"][0]
    assert match["section_title"] == "Lost or Damaged Shipments"
    assert match["source"] == "shipping_policy.md"
    assert isinstance(match["score"], int)


def test_tool_validation_errors_are_protocol_errors() -> None:
    with pytest.raises(ToolError, match="query must not be empty"):
        asyncio.run(server.mcp.call_tool("search_policy", {"query": "  "}))
