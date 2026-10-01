from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio

from app.agent.runtime import AgentRuntime
from app.llm import OllamaProvider
from app.mcp import OperationsMCPClient, PolicyMCPClient


@asynccontextmanager
async def agent_runtime(max_steps: int) -> AsyncIterator[AgentRuntime]:
    # Enter and exit SDK task groups in the same task, including partial startup.
    with anyio.CancelScope() as cleanup_scope:
        async with OperationsMCPClient() as operations:
            try:
                async with PolicyMCPClient() as policies:
                    try:
                        yield AgentRuntime(llm_provider=OllamaProvider(),
                                           mcp_client=operations,
                                           policy_mcp_client=policies,
                                           max_steps=max_steps)
                    finally:
                        cleanup_scope.shield = True
            finally:
                cleanup_scope.shield = True
