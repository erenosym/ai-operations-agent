import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from app.domain import CustomerOrderSummary, ProductLookupResult
from app.models import OrderStatus
from mcp_servers.postgres_server import server
from mcp_servers.postgres_server._serialization import to_json_compatible

EXPECTED_TOOLS = {
    "find_products",
    "get_customer_orders",
    "get_recent_refunds",
    "get_top_refunded_products",
    "get_product_statistics",
    "get_refund_reason_breakdown",
}


def test_expected_tools_and_public_input_schemas_are_registered() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    by_name = {tool.name: tool for tool in tools}

    assert set(by_name) == EXPECTED_TOOLS
    assert "execute_sql" not in by_name
    assert by_name["find_products"].input_schema["required"] == ["query"]
    assert by_name["find_products"].input_schema["properties"]["limit"]["default"] == 10
    assert by_name["get_customer_orders"].input_schema["required"] == ["customer_id"]
    assert (
        by_name["get_customer_orders"].input_schema["properties"]["limit"]["default"]
        == 50
    )
    assert (
        by_name["get_top_refunded_products"].input_schema["properties"][
            "min_sold_items"
        ]["default"]
        == 20
    )
    assert all(tool.output_schema is not None for tool in tools)
    assert all(tool.annotations.read_only_hint is True for tool in tools)


def test_find_products_delegates_and_serializes_money_as_string(monkeypatch) -> None:
    repository_call = AsyncMock(
        return_value=[
            ProductLookupResult(
                product_id=58,
                name="StridePro Running Shoes",
                category="Footwear",
                price=Decimal("94.50"),
            )
        ]
    )
    monkeypatch.setattr(server, "query_find_products", repository_call)

    result = asyncio.run(
        server.mcp.call_tool("find_products", {"query": "StridePro", "limit": 3})
    )

    repository_call.assert_awaited_once()
    assert repository_call.await_args.args[1:] == ("StridePro", 3)
    assert result.structured_content == {
        "products": [
            {
                "product_id": 58,
                "name": "StridePro Running Shoes",
                "category": "Footwear",
                "price": "94.50",
            }
        ]
    }


def test_tool_delegates_and_returns_decimal_safe_structured_output(monkeypatch) -> None:
    repository_call = AsyncMock(
        return_value=[
            CustomerOrderSummary(
                order_id=7,
                customer_id=3,
                status=OrderStatus.DELIVERED,
                ordered_at=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),
                total_amount=Decimal("129.90"),
                order_item_count=1,
                units=1,
            )
        ]
    )
    monkeypatch.setattr(server, "query_customer_orders", repository_call)

    result = asyncio.run(
        server.mcp.call_tool(
            "get_customer_orders",
            {
                "customer_id": 3,
                "start_date": "2026-09-01",
                "end_date": "2026-09-30",
                "limit": 10,
            },
        )
    )

    repository_call.assert_awaited_once()
    _, customer_id, start_date, end_date, limit = repository_call.await_args.args
    assert customer_id == 3
    assert start_date.isoformat() == "2026-09-01"
    assert end_date.isoformat() == "2026-09-30"
    assert limit == 10
    assert result.structured_content == {
        "orders": [
            {
                "order_id": 7,
                "customer_id": 3,
                "status": "delivered",
                "ordered_at": "2026-09-30T12:00:00+00:00",
                "total_amount": "129.90",
                "order_item_count": 1,
                "units": 1,
            }
        ]
    }
    assert isinstance(result.structured_content["orders"][0]["total_amount"], str)


def test_invalid_date_and_repository_validation_become_tool_errors(monkeypatch) -> None:
    with pytest.raises(ToolError, match="YYYY-MM-DD"):
        asyncio.run(
            server.mcp.call_tool(
                "get_recent_refunds",
                {"start_date": "09/01/2026", "end_date": "2026-09-30"},
            )
        )

    repository_call = AsyncMock(
        side_effect=ValueError("start_date must be on or before end_date")
    )
    monkeypatch.setattr(server, "query_recent_refunds", repository_call)
    with pytest.raises(ToolError, match="start_date must be on or before end_date"):
        asyncio.run(
            server.mcp.call_tool(
                "get_recent_refunds",
                {"start_date": "2026-10-01", "end_date": "2026-09-01"},
            )
        )


def test_generic_serializer_never_converts_decimal_to_float() -> None:
    serialized = to_json_compatible(
        {
            "money": Decimal("10.20"),
            "ratio": Decimal("0.302491"),
            "timestamp": datetime(2026, 10, 1, tzinfo=timezone.utc),
            "status": OrderStatus.PAID,
        }
    )

    assert serialized == {
        "money": "10.20",
        "ratio": "0.302491",
        "timestamp": "2026-10-01T00:00:00+00:00",
        "status": "paid",
    }
