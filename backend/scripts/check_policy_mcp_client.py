import asyncio

from app.mcp import PolicyMCPClient


async def check_client() -> None:
    async with PolicyMCPClient() as client:
        tools = await client.list_tools()
        await client.validate_expected_tools(strict=True, tools=tools)
        result = await client.search_policy("lost shipment", policy_type="shipping")
        top = result["results"][0]
        print(f"Connected to operations-policy; discovered {len(tools)} tool.")
        print(f"Top section: {top['section_title']} ({top['source']})")


def main() -> None:
    asyncio.run(check_client())


if __name__ == "__main__":
    main()
