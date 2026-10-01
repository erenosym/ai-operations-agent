"""Public observable execution events; no provider diagnostics are serialized."""
from typing import Literal

from pydantic import BaseModel, ConfigDict


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RunStarted(Event):
    type: Literal["run_started"] = "run_started"


class ToolStarted(Event):
    type: Literal["tool_started"] = "tool_started"
    step: int
    tool_name: str
    arguments: dict[str, object]


class ToolCompleted(Event):
    type: Literal["tool_completed"] = "tool_completed"
    step: int
    tool_name: str
    duration_ms: float
    result: dict[str, object]


class ToolFailed(Event):
    type: Literal["tool_failed"] = "tool_failed"
    step: int
    tool_name: str
    duration_ms: float
    message: str


class Answer(Event):
    type: Literal["answer"] = "answer"
    content: str


class RunCompleted(Event):
    type: Literal["run_completed"] = "run_completed"
    tool_calls_count: int
    termination_reason: Literal["completed"] = "completed"


class Error(Event):
    type: Literal["error"] = "error"
    code: str
    message: str = "The agent could not complete the request."


AgentEvent = RunStarted | ToolStarted | ToolCompleted | ToolFailed | Answer | RunCompleted | Error


def serialize_event(event: AgentEvent) -> str:
    return event.model_dump_json() + "\n"
