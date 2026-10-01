class MCPClientError(RuntimeError):
    """Base error for the application-side MCP boundary."""


class MCPConnectionError(MCPClientError):
    """An MCP server could not be connected to or disconnected from."""


class MCPToolCallError(MCPClientError):
    """An MCP tool invocation failed or returned an invalid result."""

    def __init__(self, tool_name: str, detail: str) -> None:
        self.tool_name = tool_name
        self.detail = detail
        super().__init__(f"MCP tool '{tool_name}' failed: {detail}")


class MCPToolValidationError(MCPClientError):
    """The server's discovered tools do not satisfy the expected contract."""

    def __init__(self, *, missing: set[str], unexpected: set[str]) -> None:
        self.missing = frozenset(missing)
        self.unexpected = frozenset(unexpected)
        details: list[str] = []
        if missing:
            details.append(f"missing tools: {', '.join(sorted(missing))}")
        if unexpected:
            details.append(f"unexpected tools: {', '.join(sorted(unexpected))}")
        message = "MCP tool validation failed (" + "; ".join(details) + ")"
        super().__init__(message)
