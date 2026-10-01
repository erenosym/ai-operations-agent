from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal, TypedDict
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.agent.api import router as agent_router

from app.database.engine import check_database_connection, engine


class ServiceHealth(TypedDict):
    database: Literal["ok", "unavailable"]


class HealthResponse(TypedDict):
    status: Literal["ok", "degraded"]
    service: str
    services: ServiceHealth


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)
app.include_router(agent_router)


@app.get("/health")
async def health() -> HealthResponse:
    try:
        await check_database_connection()
    except Exception:
        return {
            "status": "degraded",
            "service": "ai-operations-agent-api",
            "services": {"database": "unavailable"},
        }

    return {
        "status": "ok",
        "service": "ai-operations-agent-api",
        "services": {"database": "ok"},
    }
