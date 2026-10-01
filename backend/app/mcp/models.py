from dataclasses import dataclass


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str | None
    input_schema: dict[str, object]
    output_schema: dict[str, object] | None


@dataclass(frozen=True)
class MCPToolResult:
    tool_name: str
    structured_content: dict[str, object]
    is_error: bool
    text_content: tuple[str, ...] = ()
