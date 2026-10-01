import asyncio
from decimal import Decimal

import pytest

from app.llm import to_ollama_tool
from app.mcp import (
    EXPECTED_POSTGRES_TOOLS,
    MCPConnectionError,
    MCPToolCallError,
    OperationsMCPClient,
)
from mcp_servers.postgres_server.server import REFUND_RATE_DEFINITION

pytestmark = pytest.mark.integration


async def _assert_lifecycle_and_discovery() -> None:
    client = OperationsMCPClient()
    assert not client.is_connected
    async with client:
        assert client.is_connected
        tools = await client.list_tools()
        tools_by_name = {tool.name: tool for tool in tools}
        assert set(tools_by_name) == EXPECTED_POSTGRES_TOOLS
        assert "execute_sql" not in tools_by_name
        assert all(tool.description for tool in tools)
        assert all(isinstance(tool.input_schema, dict) for tool in tools)
        assert tools_by_name["find_products"].input_schema["required"] == ["query"]
        assert to_ollama_tool(tools_by_name["find_products"])["function"][
            "parameters"
        ] == tools_by_name["find_products"].input_schema
        assert tools_by_name["get_customer_orders"].input_schema["required"] == [
            "customer_id"
        ]
        assert tools_by_name["get_recent_refunds"].input_schema["required"] == [
            "start_date",
            "end_date",
        ]
        assert tools_by_name["get_top_refunded_products"].input_schema[
            "required"
        ] == ["start_date", "end_date"]
        assert tools_by_name["get_product_statistics"].input_schema["required"] == [
            "product_id",
            "start_date",
            "end_date",
        ]
        assert tools_by_name["get_refund_reason_breakdown"].input_schema[
            "required"
        ] == ["start_date", "end_date"]
        await client.validate_expected_tools(strict=True)

    assert not client.is_connected
    with pytest.raises(MCPConnectionError, match="not connected"):
        await client.list_tools()

    for _ in range(2):
        async with OperationsMCPClient() as sequential_client:
            assert sequential_client.is_connected
            await sequential_client.validate_expected_tools(strict=True)


async def _assert_real_tool_calls() -> None:
    async with OperationsMCPClient() as client:
        for query, expected_name in (
            ("StridePro Running Shoes", "StridePro Running Shoes"),
            ("Pulse Wireless", "Pulse Wireless Headphones"),
            ("Mechanical Keyboard", "Forge Mechanical Keyboard"),
        ):
            lookup = await client.find_products(query)
            matches = lookup["products"]
            assert matches
            assert matches[0]["name"] == expected_name
            assert isinstance(matches[0]["price"], str)

        top_result = await client.get_top_refunded_products(
            "2026-04-01",
            "2026-10-01",
            limit=50,
            min_sold_items=20,
        )
        assert top_result["refund_rate_definition"] == REFUND_RATE_DEFINITION
        products = top_result["products"]
        assert isinstance(products, list)
        assert [product["rank"] for product in products] == list(
            range(1, len(products) + 1)
        )
        by_name = {product["product_name"]: product for product in products}
        positions = {
            product["product_name"]: index
            for index, product in enumerate(products, start=1)
        }
        assert positions["Pulse Wireless Headphones"] <= 2
        assert positions["StridePro Running Shoes"] <= 3
        assert Decimal(by_name["Pulse Wireless Headphones"]["refund_rate"]) > Decimal(
            "0.25"
        )
        assert Decimal(by_name["Forge Mechanical Keyboard"]["refund_rate"]) < Decimal(
            "0.06"
        )
        assert isinstance(by_name["Pulse Wireless Headphones"]["refund_amount"], str)

        product_results = {}
        for product_name in (
            "Pulse Wireless Headphones",
            "StridePro Running Shoes",
            "Forge Mechanical Keyboard",
        ):
            result = await client.get_product_statistics(
                by_name[product_name]["product_id"],
                "2026-04-01",
                "2026-10-01",
            )
            assert result["found"] is True
            product_results[product_name] = result["product"]

        assert Decimal(
            product_results["Pulse Wireless Headphones"]["refund_rate"]
        ) > Decimal("0.25")
        assert (
            product_results["StridePro Running Shoes"]["most_common_refund_reason"]
            == "size_issue"
        )
        assert Decimal(
            product_results["Forge Mechanical Keyboard"]["refund_rate"]
        ) < Decimal("0.06")

        unknown = await client.get_product_statistics(
            9_999_999_999, "2026-04-01", "2026-10-01"
        )
        assert unknown == {"found": False, "product": None}

        breakdown = await client.get_refund_reason_breakdown(
            "2026-04-01",
            "2026-10-01",
            product_id=by_name["StridePro Running Shoes"]["product_id"],
        )
        reasons = breakdown["reasons"]
        assert reasons[0]["reason"] == "size_issue"
        assert all(isinstance(reason["percentage"], str) for reason in reasons)

        refunds_result = await client.get_recent_refunds(
            "2026-09-01", "2026-10-01", limit=100
        )
        refunds = refunds_result["refunds"]
        assert refunds
        assert isinstance(refunds[0]["amount"], str)
        assert refunds[0]["product_name"]

        orders_result = await client.get_customer_orders(
            refunds[0]["customer_id"],
            start_date="2026-04-01",
            end_date="2026-10-01",
            limit=100,
        )
        orders = orders_result["orders"]
        assert orders
        assert all(order["customer_id"] == refunds[0]["customer_id"] for order in orders)

        with pytest.raises(MCPToolCallError, match="start_date must be on or before"):
            await client.get_recent_refunds("2026-10-01", "2026-09-01")
        with pytest.raises(MCPToolCallError):
            await client.get_top_refunded_products(
                "2026-04-01", "2026-10-01", limit=0
            )


def test_client_lifecycle_and_tool_discovery_over_stdio() -> None:
    asyncio.run(_assert_lifecycle_and_discovery())


def test_all_tools_and_errors_over_stdio() -> None:
    asyncio.run(_assert_real_tool_calls())
