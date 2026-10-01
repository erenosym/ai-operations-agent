import argparse
import asyncio
import json

import httpx
from pydantic import TypeAdapter

from app.agent.events import AgentEvent


async def check(url: str, message: str) -> None:
    adapter = TypeAdapter(AgentEvent)
    types: list[str] = []
    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream("POST", url, json={"message": message}) as response:
            response.raise_for_status()
            assert response.headers["content-type"].startswith("application/x-ndjson")
            async for line in response.aiter_lines():
                event = adapter.validate_json(line)
                types.append(event.type)
                print(json.dumps(event.model_dump(), ensure_ascii=False), flush=True)
    assert types and types[-1] in {"run_completed", "error"}
    if types[-1] == "error":
        raise RuntimeError("Agent reported terminal failure")
    assert types[0] == "run_started"
    assert types[-2] == "answer"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/agent/run")
    parser.add_argument("--message", default="Hello.")
    args = parser.parse_args()
    asyncio.run(check(args.url, args.message))


if __name__ == "__main__":
    main()
