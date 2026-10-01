from dataclasses import dataclass
from typing import Literal

MessageRole = Literal["system", "user", "assistant", "tool"]
MessageContent = str | dict[str, object] | list[object]


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, object]
    id: str | None = None


@dataclass(frozen=True)
class ChatMessage:
    role: MessageRole
    content: MessageContent
    tool_name: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True)
class LLMResponse:
    content: str
    tool_calls: tuple[ToolCall, ...]
    finish_reason: str | None = None
