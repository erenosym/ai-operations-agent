import asyncio

from app.mcp import OperationsMCPClient


async def check_client() -> None:
    async with OperationsMCPClient() as client:
        tools = await client.list_tools()
        await client.validate_expected_tools(strict=True)
        result = await client.get_top_refunded_products(
            "2026-04-01",
            "2026-10-01",
            limit=5,
            min_sold_items=20,
        )
        products = result["products"]
        top_product = products[0] if isinstance(products, list) and products else None
        print(f"Connected to operations-postgres; discovered {len(tools)} tools.")
        if isinstance(top_product, dict):
            print(
                "Top refunded product: "
                f"{top_product['product_name']} (rate {top_product['refund_rate']})"
            )
        else:
            print("Top refunded product: none")


def main() -> None:
    asyncio.run(check_client())


if __name__ == "__main__":
    main()
