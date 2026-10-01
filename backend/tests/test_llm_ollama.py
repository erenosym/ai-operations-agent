import asyncio
from types import SimpleNamespace

import pytest

from app.llm import (
    ChatMessage,
    LLMConnectionError,
    LLMResponseError,
    OllamaProvider,
    ToolCall,
    to_ollama_message,
    to_ollama_tool,
)
from app.mcp.models import ToolDefinition


def _tool() -> ToolDefinition:
    return ToolDefinition(
        name="get_recent_refunds",
        description="Return refunds in a date range.",
        input_schema={
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "limit": {"type": "integer", "default": 100},
            },
            "required": ["start_date", "end_date"],
        },
        output_schema={"type": "object"},
    )


def test_mcp_tool_schema_is_preserved_for_ollama() -> None:
    tool = _tool()
    converted = to_ollama_tool(tool)

    assert converted == {
        "type": "function",
        "function": {
            "name": "get_recent_refunds",
            "description": "Return refunds in a date range.",
            "parameters": tool.input_schema,
        },
    }
    assert converted["function"]["parameters"]["required"] == [
        "start_date",
        "end_date",
    ]
    assert converted["function"]["parameters"]["properties"]["limit"][
        "default"
    ] == 100


def test_application_messages_convert_without_changing_structured_strings() -> None:
    assert to_ollama_message(ChatMessage(role="user", content="hello")) == {
        "role": "user",
        "content": "hello",
    }
    tool_message = to_ollama_message(
        ChatMessage(
            role="tool",
            tool_name="get_product_statistics",
            content={"amount": "10.20", "refund_rate": "0.125"},
        )
    )
    assert tool_message == {
        "role": "tool",
        "tool_name": "get_product_statistics",
        "content": '{"amount":"10.20","refund_rate":"0.125"}',
    }
    assistant_message = to_ollama_message(
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=(
                ToolCall(name="get_recent_refunds", arguments={"limit": 3}),
            ),
        )
    )
    assert assistant_message["tool_calls"] == [
        {
            "function": {
                "name": "get_recent_refunds",
                "arguments": {"limit": 3},
            }
        }
    ]


class FakeAsyncClient:
    response: object
    last_request: dict[str, object]

    def __init__(self, **kwargs: object) -> None:
        self.constructor_arguments = kwargs

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def chat(self, **kwargs: object) -> object:
        type(self).last_request = kwargs
        return type(self).response


def _response(*tool_calls: object, content: str = "", reason: str = "stop") -> object:
    return SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls)),
        done_reason=reason,
    )


def _call(name: object, arguments: object, call_id: object = None) -> object:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def test_provider_normalizes_multiple_tool_calls(monkeypatch) -> None:
    FakeAsyncClient.response = _response(
        _call("get_recent_refunds", {"limit": 3}, "provider-call-1"),
        _call("get_product_statistics", {"product_id": 1}),
    )
    monkeypatch.setattr("app.llm.ollama.ollama.AsyncClient", FakeAsyncClient)

    response = asyncio.run(
        OllamaProvider(model="test-model").chat(
            [ChatMessage(role="user", content="inspect operations")], [_tool()]
        )
    )

    assert response.tool_calls == (
        ToolCall(
            id="provider-call-1",
            name="get_recent_refunds",
            arguments={"limit": 3},
        ),
        ToolCall(name="get_product_statistics", arguments={"product_id": 1}),
    )
    assert FakeAsyncClient.last_request["model"] == "test-model"
    assert FakeAsyncClient.last_request["think"] is False
    assert FakeAsyncClient.last_request["options"] == {"temperature": 0}
    assert FakeAsyncClient.last_request["tools"] == [to_ollama_tool(_tool())]


def test_provider_parses_no_tool_response(monkeypatch) -> None:
    FakeAsyncClient.response = _response(content="Hello!", reason="stop")
    monkeypatch.setattr("app.llm.ollama.ollama.AsyncClient", FakeAsyncClient)

    response = asyncio.run(
        OllamaProvider().chat([ChatMessage(role="user", content="Hello")])
    )

    assert response.content == "Hello!"
    assert response.tool_calls == ()
    assert response.finish_reason == "stop"
    assert FakeAsyncClient.last_request["tools"] is None


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        (None, {}, "missing 'name'"),
        ("get_recent_refunds", "not-an-object", "non-object arguments"),
    ],
)
def test_provider_rejects_malformed_tool_calls(
    monkeypatch, name: object, arguments: object, message: str
) -> None:
    FakeAsyncClient.response = _response(_call(name, arguments))
    monkeypatch.setattr("app.llm.ollama.ollama.AsyncClient", FakeAsyncClient)

    with pytest.raises(LLMResponseError, match=message):
        asyncio.run(
            OllamaProvider().chat([ChatMessage(role="user", content="question")])
        )


def test_provider_normalizes_connection_failures(monkeypatch) -> None:
    class UnavailableClient(FakeAsyncClient):
        async def __aenter__(self) -> "UnavailableClient":
            raise ConnectionError("raw socket details")

    monkeypatch.setattr("app.llm.ollama.ollama.AsyncClient", UnavailableClient)

    with pytest.raises(LLMConnectionError) as error:
        asyncio.run(
            OllamaProvider().chat([ChatMessage(role="user", content="question")])
        )
    assert "raw socket details" not in str(error.value)


def test_provider_normalizes_model_errors(monkeypatch) -> None:
    class MissingModelClient(FakeAsyncClient):
        async def chat(self, **kwargs: object) -> object:
            import ollama

            raise ollama.ResponseError("model secret-model was not found", 404)

    monkeypatch.setattr("app.llm.ollama.ollama.AsyncClient", MissingModelClient)

    with pytest.raises(LLMResponseError) as error:
        asyncio.run(
            OllamaProvider().chat([ChatMessage(role="user", content="question")])
        )
    assert "secret-model" not in str(error.value)
