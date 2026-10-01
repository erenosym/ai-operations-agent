import asyncio

import pytest

from app.agent import AgentInfrastructureError, AgentMaxStepsError
from app.llm import LLMConnectionError, ToolCall
from app.mcp import MCPToolCallError
from tests.test_agent_runtime import FakeLLMProvider, FakeMCPClient, _runtime, _response, _result, _tool


def test_no_tool_stream():
    async def check():
        runtime = _runtime(FakeLLMProvider([_response("Hello")]), FakeMCPClient([]))
        events = [e async for e in runtime.run_stream("hello")]
        assert [e.type for e in events] == ["run_started", "answer", "run_completed"]
        assert events[1].content == "Hello"
    asyncio.run(check())


@pytest.mark.parametrize("count", [1, 2])
def test_tool_start_precedes_invocation_and_each_tool_runs_once(count):
    async def check():
        calls = [ToolCall(name="a", arguments={"index": i}) for i in range(count)]
        client = FakeMCPClient([_tool("a")], [_result("a", {}) for _ in calls])
        runtime = _runtime(FakeLLMProvider([_response("", *calls), _response("done")]), client)
        events = []
        async for event in runtime.run_stream("go"):
            if event.type == "tool_started":
                assert len(client.calls) == event.step - 1
            events.append(event.type)
        assert events == ["run_started"] + [item for _ in calls for item in ("tool_started", "tool_completed")] + ["answer", "run_completed"]
        assert len(client.calls) == count
    asyncio.run(check())


def test_recovery_and_consistency():
    def make():
        call = ToolCall(name="a", arguments={})
        return _runtime(FakeLLMProvider([_response("", call), _response("", call), _response("done")]),
                        FakeMCPClient([_tool("a")], [MCPToolCallError("a", "invalid"), _result("a", {"value": "10.20"})]))
    async def check():
        events = [e async for e in make().run_stream("go")]
        result = await make().run("go")
        assert [e.type for e in events] == ["run_started", "tool_started", "tool_failed", "tool_started", "tool_completed", "answer", "run_completed"]
        assert result.answer == events[-2].content
        assert result.tool_calls_count == events[-1].tool_calls_count == 2
        assert result.steps[1].structured_result == events[4].result
    asyncio.run(check())


@pytest.mark.parametrize("maximum", [False, True])
def test_terminal_stream_failure(maximum):
    async def check():
        responses = [_response("", ToolCall(name="a", arguments={}))] if maximum else [LLMConnectionError("offline")]
        runtime = _runtime(FakeLLMProvider(responses), FakeMCPClient([_tool("a")], [_result("a", {})]), max_steps=1)
        events = []
        with pytest.raises(AgentMaxStepsError if maximum else AgentInfrastructureError):
            async for event in runtime.run_stream("go"):
                events.append(event.type)
        assert events[0] == "run_started"
        assert "run_completed" not in events
    asyncio.run(check())
