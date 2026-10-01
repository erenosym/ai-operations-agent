class AgentRuntimeError(RuntimeError):
    """Base error for the manual agent orchestration boundary."""


class AgentInfrastructureError(AgentRuntimeError):
    """An LLM or MCP infrastructure dependency failed."""


class AgentResponseError(AgentRuntimeError):
    """The model returned an incomplete response."""


class AgentMaxStepsError(AgentRuntimeError):
    """The agent exhausted its bounded model/tool loop."""

    def __init__(self, max_steps: int, tool_calls_count: int) -> None:
        self.max_steps = max_steps
        self.tool_calls_count = tool_calls_count
        super().__init__(
            f"Agent did not produce a final answer within {max_steps} steps"
        )
