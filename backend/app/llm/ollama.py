from collections.abc import Mapping
import json
from typing import Any, cast

import httpx
import ollama

from app.config import load_ollama_settings
from app.llm.models import ChatMessage, LLMResponse, ToolCall
from app.llm.provider import LLMConnectionError, LLMResponseError
from app.mcp.models import ToolDefinition

OPERATIONS_SYSTEM_PROMPT = (
    "You are an e-commerce operations assistant. Use tools for operational facts "
    "and retrieve policies for operational rules; use multiple tools when both are "
    "needed. Never invent data, rules, or identifiers. CRITICAL: for a dependent "
    "call, copy the selected row's explicit ID field digit for digit. A rank or list "
    "position is never an entity ID, and another row's ID is never a substitute. "
    "Resolve named entities with an available lookup capability. Use relevant exact "
    "labels from tool results in later policy lookups. Continue until every requested "
    "part is supported, then answer clearly and mention the policy source or section "
    "when appropriate. Do not call tools for casual questions."
)


def to_ollama_tool(tool: ToolDefinition) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }


def to_ollama_message(message: ChatMessage) -> dict[str, object]:
    content = (
        message.content
        if isinstance(message.content, str)
        else json.dumps(message.content, separators=(",", ":"), sort_keys=True)
    )
    provider_message: dict[str, object] = {
        "role": message.role,
        "content": content,
    }
    if message.tool_name is not None:
        provider_message["tool_name"] = message.tool_name
    if message.tool_calls:
        provider_message["tool_calls"] = [
            {
                "function": {
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                }
            }
            for tool_call in message.tool_calls
        ]
    return provider_message


class OllamaProvider:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        settings = load_ollama_settings()
        self.base_url = base_url or settings.base_url
        self.model = model or settings.model
        self.timeout_seconds = timeout_seconds

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        provider_messages = [to_ollama_message(message) for message in messages]
        provider_tools = [to_ollama_tool(tool) for tool in tools] if tools else None
        try:
            async with ollama.AsyncClient(
                host=self.base_url, timeout=self.timeout_seconds
            ) as client:
                response = await client.chat(
                    model=self.model,
                    messages=provider_messages,
                    tools=provider_tools,
                    think=False,
                    options={"temperature": 0},
                )
        except (ConnectionError, httpx.TimeoutException, TimeoutError) as error:
            raise LLMConnectionError(
                "Could not reach the configured Ollama service in time"
            ) from error
        except (ollama.RequestError, ollama.ResponseError) as error:
            raise LLMResponseError(
                "Ollama rejected the request or the configured model is unavailable"
            ) from error
        except Exception as error:
            raise LLMResponseError("Ollama returned an invalid response") from error

        try:
            content = response.message.content or ""
            tool_calls = tuple(
                _parse_tool_call(tool_call)
                for tool_call in (response.message.tool_calls or ())
            )
            finish_reason = response.done_reason
        except LLMResponseError:
            raise
        except Exception as error:
            raise LLMResponseError("Ollama returned a malformed message") from error

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
        )


def _parse_tool_call(provider_call: object) -> ToolCall:
    function = _field(provider_call, "function")
    name = _field(function, "name")
    arguments = _field(function, "arguments")
    call_id = _field(provider_call, "id", required=False)

    if not isinstance(name, str) or not name.strip():
        raise LLMResponseError("Ollama returned a tool call without a valid name")
    if not isinstance(arguments, Mapping):
        raise LLMResponseError(
            f"Ollama returned non-object arguments for tool '{name}'"
        )
    if call_id is not None and not isinstance(call_id, str):
        raise LLMResponseError(f"Ollama returned an invalid ID for tool '{name}'")

    return ToolCall(
        id=call_id,
        name=name,
        arguments=cast(dict[str, object], dict(arguments)),
    )


def _field(value: object, name: str, *, required: bool = True) -> Any:
    if isinstance(value, Mapping):
        field = value.get(name)
    else:
        field = getattr(value, name, None)
    if required and field is None:
        raise LLMResponseError(f"Ollama response is missing '{name}'")
    return field
