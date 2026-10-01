import asyncio
from collections.abc import Mapping
import os
from pathlib import Path
import sys

from mcp import Client, StdioServerParameters

from app.mcp.errors import MCPConnectionError, MCPToolCallError, MCPToolValidationError
from app.mcp.models import MCPToolResult, ToolDefinition

EXPECTED_POLICY_TOOLS = frozenset({"search_policy"})


class PolicyMCPClient:
    """Application client for the operations-policy stdio MCP server."""

    def __init__(
        self,
        *,
        startup_timeout_seconds: float = 10.0,
        request_timeout_seconds: float = 30.0,
        repository_root: Path | None = None,
    ) -> None:
        self._startup_timeout_seconds = startup_timeout_seconds
        self._request_timeout_seconds = request_timeout_seconds
        self._repository_root = repository_root or Path(__file__).resolve().parents[3]
        self._sdk_client: Client | None = None

    async def __aenter__(self) -> "PolicyMCPClient":
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
            raise MCPConnectionError("Policy MCP client is already connected")
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_servers.policy_server.server"],
            cwd=self._repository_root,
            env={
                "PYTHONPATH": os.pathsep.join(
                    (str(self._repository_root), str(self._repository_root / "backend"))
                )
            },
        )
        sdk_client = Client(parameters, read_timeout_seconds=self._request_timeout_seconds)
        try:
            async with asyncio.timeout(self._startup_timeout_seconds):
                await sdk_client.__aenter__()
        except Exception as error:
            try:
                await sdk_client.__aexit__(type(error), error, error.__traceback__)
            except Exception:
                pass
            raise MCPConnectionError("Could not connect to the policy MCP server") from error
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
                "Could not close the policy MCP connection cleanly"
            ) from error

    def _connected_client(self) -> Client:
        if self._sdk_client is None:
            raise MCPConnectionError("Policy MCP client is not connected")
        return self._sdk_client

    async def list_tools(self) -> list[ToolDefinition]:
        try:
            result = await self._connected_client().list_tools()
        except MCPConnectionError:
            raise
        except Exception as error:
            raise MCPConnectionError("Could not discover policy MCP tools") from error
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
        missing = set(EXPECTED_POLICY_TOOLS - discovered)
        unexpected = set(discovered - EXPECTED_POLICY_TOOLS) if strict else set()
        if missing or unexpected:
            raise MCPToolValidationError(missing=missing, unexpected=unexpected)

    async def call_tool(
        self, name: str, arguments: Mapping[str, object]
    ) -> MCPToolResult:
        try:
            result = await self._connected_client().call_tool(name, dict(arguments))
        except MCPConnectionError:
            raise
        except Exception as error:
            raise MCPConnectionError("Policy MCP tool invocation failed") from error
        text_content = tuple(
            text
            for block in result.content
            if isinstance((text := getattr(block, "text", None)), str)
        )
        if result.is_error:
            raise MCPToolCallError(
                name, "; ".join(text_content) or "server returned a tool error"
            )
        if not isinstance(result.structured_content, dict):
            raise MCPToolCallError(name, "server returned no structured object result")
        return MCPToolResult(
            tool_name=name,
            structured_content=dict(result.structured_content),
            is_error=False,
            text_content=text_content,
        )

    async def search_policy(
        self,
        query: str,
        *,
        policy_type: str | None = None,
        limit: int = 5,
    ) -> dict[str, object]:
        arguments: dict[str, object] = {"query": query, "limit": limit}
        if policy_type is not None:
            arguments["policy_type"] = policy_type
        return (await self.call_tool("search_policy", arguments)).structured_content
