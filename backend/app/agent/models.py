from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AgentStep:
    step_number: int
    tool_name: str
    arguments: dict[str, object]
    success: bool
    duration_ms: float
    error: str | None = None
    structured_result: dict[str, object] | None = None


@dataclass(frozen=True)
class AgentResult:
    answer: str
    steps: tuple[AgentStep, ...]
    tool_calls_count: int
    termination_reason: Literal["completed"]
