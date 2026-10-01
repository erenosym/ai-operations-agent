import asyncio
from collections.abc import Mapping
from datetime import date
import os
from pathlib import Path
import sys

from mcp import Client, StdioServerParameters

from app.mcp.errors import (
    MCPConnectionError,
    MCPToolCallError,
    MCPToolValidationError,
)
from app.mcp.models import MCPToolResult, ToolDefinition

EXPECTED_POSTGRES_TOOLS = frozenset(
    {
        "find_products",
        "get_customer_orders",
        "get_recent_refunds",
        "get_top_refunded_products",
        "get_product_statistics",
        "get_refund_reason_breakdown",
    }
)


class OperationsMCPClient:
    """Application client for the operations-postgres stdio MCP server."""

    def __init__(
        self,
        database_url: str | None = None,
        *,
        startup_timeout_seconds: float = 10.0,
        request_timeout_seconds: float = 30.0,
        repository_root: Path | None = None,
    ) -> None:
        self._database_url = database_url or os.getenv("DATABASE_URL")
        self._startup_timeout_seconds = startup_timeout_seconds
        self._request_timeout_seconds = request_timeout_seconds
        self._repository_root = repository_root or Path(__file__).resolve().parents[3]
        self._sdk_client: Client | None = None

    async def __aenter__(self) -> "OperationsMCPClient":
        await self.connect()
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: object,
    ) -> None:
        await self.disconnect()

    @property
    def is_connected(self) -> bool:
        return self._sdk_client is not None

    async def connect(self) -> None:
        if self.is_connected:
            raise MCPConnectionError("Operations MCP client is already connected")
        if not self._database_url:
            raise MCPConnectionError(
                "DATABASE_URL is required to start the operations MCP server"
            )

        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_servers.postgres_server.server"],
            cwd=self._repository_root,
            env={
                "PYTHONPATH": os.pathsep.join(
                    (str(self._repository_root), str(self._repository_root / "backend"))
                ),
                "DATABASE_URL": self._database_url,
            },
        )
        sdk_client = Client(
            parameters,
            read_timeout_seconds=self._request_timeout_seconds,
        )
        try:
            async with asyncio.timeout(self._startup_timeout_seconds):
                await sdk_client.__aenter__()
        except Exception as error:
            try:
                await sdk_client.__aexit__(type(error), error, error.__traceback__)
            except Exception:
                pass
            raise MCPConnectionError(
                "Could not connect to the operations MCP server"
            ) from error
        self._sdk_client = sdk_client

    async def disconnect(self) -> None:
        sdk_client = self._sdk_client
        self._sdk_client = None
        if sdk_client is None:
            return
        try:
            await sdk_client.__aexit__(None, None, None)
        except Exception as error:
            raise MCPConnectionError(
                "Could not close the operations MCP connection cleanly"
            ) from error

    def _connected_client(self) -> Client:
        if self._sdk_client is None:
            raise MCPConnectionError("Operations MCP client is not connected")
        return self._sdk_client

    async def list_tools(self) -> list[ToolDefinition]:
        try:
            result = await self._connected_client().list_tools()
        except MCPConnectionError:
            raise
        except Exception as error:
            raise MCPConnectionError(
                "Could not discover operations MCP tools"
            ) from error

        return [
            ToolDefinition(
                name=tool.name,
                description=tool.description,
                input_schema=dict(tool.input_schema),
                output_schema=(
                    dict(tool.output_schema) if tool.output_schema is not None else None
                ),
            )
            for tool in result.tools
        ]

    async def validate_expected_tools(
        self,
        *,
        strict: bool = False,
        tools: list[ToolDefinition] | None = None,
    ) -> None:
        discovered_tools = tools if tools is not None else await self.list_tools()
        discovered = {tool.name for tool in discovered_tools}
        missing = set(EXPECTED_POSTGRES_TOOLS - discovered)
        unexpected = set(discovered - EXPECTED_POSTGRES_TOOLS) if strict else set()
        unexpected.update(discovered & {"execute_sql"})
        if missing or unexpected:
            raise MCPToolValidationError(missing=missing, unexpected=unexpected)

    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, object],
    ) -> MCPToolResult:
        try:
            result = await self._connected_client().call_tool(name, dict(arguments))
        except MCPConnectionError:
            raise
        except Exception as error:
            raise MCPConnectionError(
                "Operations MCP tool invocation failed"
            ) from error

        text_content = tuple(
            text
            for block in result.content
            if isinstance((text := getattr(block, "text", None)), str)
        )
        if result.is_error:
            detail = "; ".join(text_content) or "server returned a tool error"
            if self._database_url:
                detail = detail.replace(self._database_url, "[redacted]")
            raise MCPToolCallError(name, detail)
        if not isinstance(result.structured_content, dict):
            raise MCPToolCallError(
                name, "server returned no structured object result"
            )

        return MCPToolResult(
            tool_name=name,
            structured_content=dict(result.structured_content),
            is_error=False,
            text_content=text_content,
        )

    async def get_customer_orders(
        self,
        customer_id: int,
        *,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        arguments: dict[str, object] = {"customer_id": customer_id, "limit": limit}
        if start_date is not None:
            arguments["start_date"] = _date_string(start_date)
        if end_date is not None:
            arguments["end_date"] = _date_string(end_date)
        return (await self.call_tool("get_customer_orders", arguments)).structured_content

    async def find_products(
        self, query: str, *, limit: int = 10
    ) -> dict[str, object]:
        return (
            await self.call_tool(
                "find_products",
                {"query": query, "limit": limit},
            )
        ).structured_content

    async def get_recent_refunds(
        self, start_date: date | str, end_date: date | str, *, limit: int = 100
    ) -> dict[str, object]:
        return (
            await self.call_tool(
                "get_recent_refunds",
                {
                    "start_date": _date_string(start_date),
                    "end_date": _date_string(end_date),
                    "limit": limit,
                },
            )
        ).structured_content

    async def get_top_refunded_products(
        self,
        start_date: date | str,
        end_date: date | str,
        *,
        limit: int = 5,
        min_sold_items: int = 20,
    ) -> dict[str, object]:
        return (
            await self.call_tool(
                "get_top_refunded_products",
                {
                    "start_date": _date_string(start_date),
                    "end_date": _date_string(end_date),
                    "limit": limit,
                    "min_sold_items": min_sold_items,
                },
            )
        ).structured_content

    async def get_product_statistics(
        self, product_id: int, start_date: date | str, end_date: date | str
    ) -> dict[str, object]:
        return (
            await self.call_tool(
                "get_product_statistics",
                {
                    "product_id": product_id,
                    "start_date": _date_string(start_date),
                    "end_date": _date_string(end_date),
                },
            )
        ).structured_content

    async def get_refund_reason_breakdown(
        self,
        start_date: date | str,
        end_date: date | str,
        *,
        product_id: int | None = None,
    ) -> dict[str, object]:
        arguments: dict[str, object] = {
            "start_date": _date_string(start_date),
            "end_date": _date_string(end_date),
        }
        if product_id is not None:
            arguments["product_id"] = product_id
        return (
            await self.call_tool("get_refund_reason_breakdown", arguments)
        ).structured_content


def _date_string(value: date | str) -> str:
    return value.isoformat() if isinstance(value, date) else value
