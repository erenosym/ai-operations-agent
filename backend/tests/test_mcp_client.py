import asyncio
from types import SimpleNamespace

import pytest

from app.mcp import (
    EXPECTED_POSTGRES_TOOLS,
    MCPConnectionError,
    MCPToolCallError,
    MCPToolValidationError,
    OperationsMCPClient,
)


class StubSDKClient:
    def __init__(self, *, tools: list[object] | None = None, result: object = None):
        self.tools = tools or []
        self.result = result
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def list_tools(self) -> object:
        return SimpleNamespace(tools=self.tools)

    async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        self.calls.append((name, arguments))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _tool(name: str) -> object:
    return SimpleNamespace(
        name=name,
        description=f"Description for {name}",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )


def test_discovery_returns_application_models_and_validates_allow_list() -> None:
    async def run() -> None:
        client = OperationsMCPClient("postgresql+asyncpg://unused")
        client._sdk_client = StubSDKClient(  # type: ignore[assignment]
            tools=[_tool(name) for name in EXPECTED_POSTGRES_TOOLS]
        )
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == EXPECTED_POSTGRES_TOOLS
        assert all(isinstance(tool.input_schema, dict) for tool in tools)
        await client.validate_expected_tools(strict=True)

        client._sdk_client = StubSDKClient(  # type: ignore[assignment]
            tools=[_tool("execute_sql")]
        )
        with pytest.raises(MCPToolValidationError) as error:
            await client.validate_expected_tools()
        assert error.value.missing == EXPECTED_POSTGRES_TOOLS
        assert error.value.unexpected == {"execute_sql"}

    asyncio.run(run())


def test_call_tool_preserves_structured_strings_and_raises_for_tool_errors() -> None:
    async def run() -> None:
        client = OperationsMCPClient("postgresql+asyncpg://user:secret@host/db")
        client._sdk_client = StubSDKClient(  # type: ignore[assignment]
            result=SimpleNamespace(
                is_error=False,
                structured_content={"amount": "10.20", "ratio": "0.125"},
                content=[SimpleNamespace(text="diagnostic")],
            )
        )
        result = await client.call_tool("example", {})
        assert result.structured_content == {"amount": "10.20", "ratio": "0.125"}
        assert result.text_content == ("diagnostic",)
        assert result.is_error is False

        client._sdk_client.result = SimpleNamespace(  # type: ignore[union-attr]
            is_error=True,
            structured_content=None,
            content=[SimpleNamespace(text="invalid limit")],
        )
        with pytest.raises(MCPToolCallError, match="invalid limit"):
            await client.call_tool("example", {})

        client._sdk_client.result = SimpleNamespace(  # type: ignore[union-attr]
            is_error=False, structured_content=None, content=[]
        )
        with pytest.raises(MCPToolCallError, match="no structured object"):
            await client.call_tool("example", {})

    asyncio.run(run())


def test_operations_require_an_active_connection() -> None:
    client = OperationsMCPClient("postgresql+asyncpg://unused")
    with pytest.raises(MCPConnectionError, match="not connected"):
        asyncio.run(client.list_tools())


def test_find_products_wrapper_only_constructs_protocol_arguments() -> None:
    async def run() -> None:
        client = OperationsMCPClient("postgresql+asyncpg://unused")
        sdk = StubSDKClient(
            result=SimpleNamespace(
                is_error=False,
                structured_content={
                    "products": [
                        {
                            "product_id": 58,
                            "name": "StridePro Running Shoes",
                            "category": "Footwear",
                            "price": "94.50",
                        }
                    ]
                },
                content=[],
            )
        )
        client._sdk_client = sdk  # type: ignore[assignment]

        result = await client.find_products("StridePro", limit=3)

        assert result["products"][0]["price"] == "94.50"
        assert sdk.calls == [("find_products", {"query": "StridePro", "limit": 3})]

    asyncio.run(run())


def test_protocol_invocation_failure_is_an_infrastructure_error() -> None:
    async def run() -> None:
        failure = OSError("transport closed")
        client = OperationsMCPClient("postgresql+asyncpg://unused")
        client._sdk_client = StubSDKClient(result=failure)  # type: ignore[assignment]

        with pytest.raises(MCPConnectionError) as error:
            await client.call_tool("get_recent_refunds", {})
        assert error.value.__cause__ is failure

    asyncio.run(run())
