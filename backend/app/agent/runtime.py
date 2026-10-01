import logging
from collections.abc import AsyncIterator
from time import perf_counter

from app.agent.errors import (
    AgentInfrastructureError,
    AgentMaxStepsError,
    AgentResponseError,
)
from app.agent.models import AgentResult, AgentStep
from app.agent.events import (
    AgentEvent, Answer, RunStarted, RunCompleted, ToolStarted, ToolCompleted, ToolFailed,
)
from app.llm import ChatMessage, LLMProvider, OPERATIONS_SYSTEM_PROMPT
from app.llm.provider import LLMProviderError
from app.mcp import (
    MCPConnectionError,
    MCPToolCallError,
    MCPToolValidationError,
    OperationsMCPClient,
    PolicyMCPClient,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_STEPS = 5
MAX_ALLOWED_STEPS = 10


class AgentRuntime:
    """A small, bounded LLM → MCP tool → observation loop."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        mcp_client: OperationsMCPClient,
        policy_mcp_client: PolicyMCPClient | None = None,
        max_steps: int = DEFAULT_MAX_STEPS,
    ) -> None:
        if not 1 <= max_steps <= MAX_ALLOWED_STEPS:
            raise ValueError(
                f"max_steps must be between 1 and {MAX_ALLOWED_STEPS}"
            )
        self._llm_provider = llm_provider
        self._mcp_client = mcp_client
        self._policy_mcp_client = policy_mcp_client
        self._max_steps = max_steps

    async def run(self, user_message: str) -> AgentResult:
        trace: list[AgentStep] = []
        arguments: dict[int, dict[str, object]] = {}
        answer = ""
        async for event in self.run_stream(user_message):
            if isinstance(event, ToolStarted):
                arguments[event.step] = event.arguments
            elif isinstance(event, (ToolCompleted, ToolFailed)):
                trace.append(AgentStep(
                    step_number=event.step, tool_name=event.tool_name,
                    arguments=arguments[event.step],
                    success=isinstance(event, ToolCompleted),
                    duration_ms=event.duration_ms,
                    structured_result=event.result if isinstance(event, ToolCompleted) else None,
                    error=event.message if isinstance(event, ToolFailed) else None,
                ))
            elif isinstance(event, Answer):
                answer = event.content
        return AgentResult(answer=answer, steps=tuple(trace),
                           tool_calls_count=len(trace), termination_reason="completed")

    async def run_stream(self, user_message: str) -> AsyncIterator[AgentEvent]:
        if not user_message.strip():
            raise ValueError("user_message must not be empty")

        logger.info("Agent run started")
        yield RunStarted()
        try:
            clients: list[OperationsMCPClient | PolicyMCPClient] = [
                self._mcp_client
            ]
            if self._policy_mcp_client is not None:
                clients.append(self._policy_mcp_client)
            tools = []
            tool_owners: dict[str, OperationsMCPClient | PolicyMCPClient] = {}
            for client in clients:
                client_tools = await client.list_tools()
                await client.validate_expected_tools(strict=True, tools=client_tools)
                for tool in client_tools:
                    if tool.name in tool_owners:
                        raise MCPToolValidationError(
                            missing=set(), unexpected={f"duplicate:{tool.name}"}
                        )
                    tools.append(tool)
                    tool_owners[tool.name] = client
        except (MCPConnectionError, MCPToolValidationError) as error:
            raise AgentInfrastructureError(
                "Agent could not discover its MCP tools"
            ) from error

        allowed_tools = set(tool_owners)
        messages = [
            ChatMessage(role="system", content=OPERATIONS_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_message),
        ]
        trace: list[AgentStep] = []

        for _ in range(self._max_steps):
            try:
                response = await self._llm_provider.chat(messages, tools)
            except LLMProviderError as error:
                raise AgentInfrastructureError(
                    "Agent could not obtain a model response"
                ) from error

            if not response.tool_calls:
                answer = response.content.strip()
                if not answer:
                    raise AgentResponseError(
                        "Model returned neither tool calls nor a final answer"
                    )
                logger.info("Agent run completed with %d tool calls", len(trace))
                yield Answer(content=answer)
                yield RunCompleted(tool_calls_count=len(trace))
                return

            messages.append(
                ChatMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )
            for tool_call in response.tool_calls:
                step_number = len(trace) + 1
                logger.info("Agent requested tool %s", tool_call.name)
                yield ToolStarted(step=step_number, tool_name=tool_call.name,
                                  arguments=dict(tool_call.arguments))
                if tool_call.name not in allowed_tools:
                    error_message = f"Tool '{tool_call.name}' is not available"
                    trace.append(
                        AgentStep(
                            step_number=step_number,
                            tool_name=tool_call.name,
                            arguments=dict(tool_call.arguments),
                            success=False,
                            duration_ms=0.0,
                            error=error_message,
                        )
                    )
                    messages.append(
                        ChatMessage(
                            role="tool",
                            tool_name=tool_call.name,
                            content={"error": True, "message": error_message},
                        )
                    )
                    logger.warning("Agent rejected unknown tool %s", tool_call.name)
                    yield ToolFailed(step=step_number, tool_name=tool_call.name,
                                     duration_ms=0.0, message=error_message)
                    continue

                started_at = perf_counter()
                try:
                    result = await tool_owners[tool_call.name].call_tool(
                        tool_call.name, tool_call.arguments
                    )
                except MCPToolCallError as error:
                    duration_ms = _elapsed_ms(started_at)
                    trace.append(
                        AgentStep(
                            step_number=step_number,
                            tool_name=tool_call.name,
                            arguments=dict(tool_call.arguments),
                            success=False,
                            duration_ms=duration_ms,
                            error=error.detail,
                        )
                    )
                    messages.append(
                        ChatMessage(
                            role="tool",
                            tool_name=tool_call.name,
                            content={"error": True, "message": error.detail},
                        )
                    )
                    logger.info("Agent tool %s failed", tool_call.name)
                    yield ToolFailed(step=step_number, tool_name=tool_call.name,
                                     duration_ms=duration_ms, message=error.detail)
                    continue
                except MCPConnectionError as error:
                    raise AgentInfrastructureError(
                        "Agent lost an MCP connection"
                    ) from error

                duration_ms = _elapsed_ms(started_at)
                structured_result = dict(result.structured_content)
                trace.append(
                    AgentStep(
                        step_number=step_number,
                        tool_name=tool_call.name,
                        arguments=dict(tool_call.arguments),
                        success=True,
                        duration_ms=duration_ms,
                        structured_result=structured_result,
                    )
                )
                messages.append(
                    ChatMessage(
                        role="tool",
                        tool_name=tool_call.name,
                        content=structured_result,
                    )
                )
                logger.info(
                    "Agent tool %s completed in %.2f ms",
                    tool_call.name,
                    duration_ms,
                )
                yield ToolCompleted(step=step_number, tool_name=tool_call.name,
                                    duration_ms=duration_ms, result=structured_result)

        logger.warning("Agent reached max_steps=%d", self._max_steps)
        raise AgentMaxStepsError(self._max_steps, len(trace))


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
