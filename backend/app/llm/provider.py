from typing import Protocol

from app.llm.models import ChatMessage, LLMResponse
from app.mcp.models import ToolDefinition


class LLMProviderError(RuntimeError):
    """Base error for an LLM provider boundary."""


class LLMConnectionError(LLMProviderError):
    """The configured LLM provider could not be reached in time."""


class LLMResponseError(LLMProviderError):
    """The provider rejected the request or returned a malformed response."""


class LLMProvider(Protocol):
    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse: ...
