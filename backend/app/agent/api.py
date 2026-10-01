import asyncio
from collections.abc import AsyncIterator
from contextlib import aclosing
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agent.errors import AgentInfrastructureError, AgentMaxStepsError, AgentResponseError
from app.agent.events import Error, ToolFailed, serialize_event
from app.agent.factory import agent_runtime
from app.agent.runtime import DEFAULT_MAX_STEPS, MAX_ALLOWED_STEPS

logger = logging.getLogger(__name__)
router = APIRouter()


class AgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=10000)
    max_steps: int | None = Field(default=None, ge=1, le=MAX_ALLOWED_STEPS, strict=True)

    @field_validator("message", mode="before")
    @classmethod
    def trim_message(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


async def stream_run(body: AgentRunRequest) -> AsyncIterator[str]:
    logger.info("API agent run started")
    try:
        async with agent_runtime(body.max_steps or DEFAULT_MAX_STEPS) as runtime:
            async with aclosing(runtime.run_stream(body.message)) as events:
                async for event in events:
                    # Raw server error details remain available to the runtime for
                    # recovery, but never cross the public HTTP boundary.
                    if isinstance(event, ToolFailed):
                        event = event.model_copy(update={"message": "Tool invocation failed."})
                    yield serialize_event(event)
    except asyncio.CancelledError:
        logger.info("API agent run cancelled by client")
        raise
    except Exception as error:
        codes = {
            AgentInfrastructureError: "agent_infrastructure_error",
            AgentMaxStepsError: "agent_max_steps_error",
            AgentResponseError: "agent_response_error",
        }
        # Exception class only: dependency exceptions can contain credentials.
        logger.error("API agent run failed (%s)", type(error).__name__)
        yield serialize_event(Error(code=codes.get(type(error), "agent_infrastructure_error")))
    finally:
        logger.info("API agent run ended")


@router.post("/agent/run", response_class=StreamingResponse, responses={
    200: {"description": "NDJSON event stream. Late failures are error events, not HTTP status changes.",
          "content": {"application/x-ndjson": {"schema": {"type": "string"}}}},
})
async def run_agent(body: AgentRunRequest) -> StreamingResponse:
    return StreamingResponse(stream_run(body), media_type="application/x-ndjson")
