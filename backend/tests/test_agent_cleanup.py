import asyncio
from contextlib import asynccontextmanager

import anyio
import pytest

from app.agent import api, factory
from app.agent.events import RunStarted


def test_cancelled_stream_closes_runtime(monkeypatch):
    closed = []
    class Runtime:
        async def run_stream(self, message):
            yield RunStarted()
            await asyncio.Event().wait()
    @asynccontextmanager
    async def compose(max_steps):
        try:
            yield Runtime()
        finally:
            closed.append(True)
    monkeypatch.setattr(api, "agent_runtime", compose)
    async def check():
        stream = api.stream_run(api.AgentRunRequest(message="hello"))
        await anext(stream)
        task = asyncio.create_task(anext(stream))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert closed == [True]
    asyncio.run(check())


@pytest.mark.parametrize("partial_startup", [False, True])
def test_factory_closes_resources_on_cancellation_or_partial_startup(monkeypatch, partial_startup):
    closed = []
    class Client:
        def __init__(self, name):
            self.name = name
        async def __aenter__(self):
            if partial_startup and self.name == "policy":
                raise RuntimeError("startup failed")
            return self
        async def __aexit__(self, *args):
            await anyio.sleep(0)
            closed.append(self.name)
    monkeypatch.setattr(factory, "OperationsMCPClient", lambda: Client("operations"))
    monkeypatch.setattr(factory, "PolicyMCPClient", lambda: Client("policy"))
    async def check():
        if partial_startup:
            with pytest.raises(RuntimeError):
                async with factory.agent_runtime(5):
                    pass
            assert closed == ["operations"]
        else:
            with anyio.CancelScope() as scope:
                async with factory.agent_runtime(5):
                    scope.cancel()
                    await anyio.sleep(0)
            assert closed == ["policy", "operations"]
    anyio.run(check)
