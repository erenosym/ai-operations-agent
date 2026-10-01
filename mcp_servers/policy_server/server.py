from dataclasses import asdict
from typing import cast

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from app.policies import search_policy as search_policy_sections
from mcp_servers.policy_server._types import PolicySearchOutput, PolicySearchResponse

READ_ONLY_TOOL = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

mcp = MCPServer[None](
    name="operations-policy",
    title="AI Operations Policies",
    description="Read-only operational policy lookup tools.",
    version="0.1.0",
)


@mcp.tool(annotations=READ_ONLY_TOOL, structured_output=True)
def search_policy(
    query: str,
    policy_type: str | None = None,
    limit: int = 5,
) -> PolicySearchResponse:
    """Search operational refund, return, and shipping policy sections."""
    try:
        results = search_policy_sections(query, policy_type, limit)
    except ValueError as error:
        raise ToolError(str(error)) from error

    output: list[PolicySearchOutput] = []
    for result in results:
        serialized = asdict(result)
        serialized["source"] = serialized.pop("source_path")
        output.append(cast(PolicySearchOutput, serialized))
    return {"results": output}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
