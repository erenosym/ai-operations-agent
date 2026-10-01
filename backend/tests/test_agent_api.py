from contextlib import asynccontextmanager
import json

from fastapi.testclient import TestClient
import pytest

from app.agent import api
from app.agent.events import Answer, RunStarted, RunCompleted, ToolStarted, ToolCompleted, ToolFailed
from app.agent.errors import AgentInfrastructureError
from app.main import app


@pytest.fixture
def install(monkeypatch):
    closed = []
    def set_events(events):
        class Runtime:
            async def run_stream(self, message):
                for event in events:
                    if isinstance(event, Exception):
                        raise event
                    yield event
        @asynccontextmanager
        async def factory(max_steps):
            try:
                yield Runtime()
            finally:
                closed.append(True)
        monkeypatch.setattr(api, "agent_runtime", factory)
    return set_events, closed


def test_stream_order_serialization_and_recovery(install):
    setup, closed = install
    setup([RunStarted(), ToolStarted(step=1, tool_name="search_policy", arguments={}),
           ToolFailed(step=1, tool_name="search_policy", duration_ms=1, message="secret"),
           ToolStarted(step=2, tool_name="search_policy", arguments={}),
           ToolCompleted(step=2, tool_name="search_policy", duration_ms=1,
                         result={"amount": "10.20", "text": "a\nb"}),
           Answer(content="done\nnow"), RunCompleted(tool_calls_count=2)])
    response = TestClient(app).post("/agent/run", json={"message": " hi "})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-ndjson"
    events = [json.loads(line) for line in response.text.splitlines()]
    assert [event["type"] for event in events] == ["run_started", "tool_started", "tool_failed", "tool_started", "tool_completed", "answer", "run_completed"]
    assert "secret" not in response.text
    assert events[4]["result"]["amount"] == "10.20"
    assert closed == [True]
    assert not any(key in response.text for key in ["thinking", "reasoning", "chain_of_thought"])


@pytest.mark.parametrize("body", [{"message": " "}, {"message": "x" * 10001},
    {"message": "x", "max_steps": 0}, {"message": "x", "max_steps": 11},
    {"message": "x", "max_steps": True}, {"message": "x", "model": "x"}])
def test_invalid_requests_fail_before_stream(body):
    assert TestClient(app).post("/agent/run", json=body).status_code == 422


def test_terminal_failure_is_safe_and_closes(install):
    setup, closed = install
    setup([RunStarted(), AgentInfrastructureError("postgres://secret traceback")])
    response = TestClient(app).post("/agent/run", json={"message": "hello"})
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines()]
    assert [event["type"] for event in events] == ["run_started", "error"]
    assert events[-1]["code"] == "agent_infrastructure_error"
    assert "secret" not in response.text
    assert closed == [True]


def test_openapi_documents_ndjson():
    schema = TestClient(app).get("/openapi.json").json()
    assert "application/x-ndjson" in schema["paths"]["/agent/run"]["post"]["responses"]["200"]["content"]
