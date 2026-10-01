from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
import re
from typing import cast

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from app.database.engine import engine
from app.database.session import async_session_factory
from app.repositories.orders import get_customer_orders as query_customer_orders
from app.repositories.products import find_products as query_find_products
from app.repositories.products import (
    get_product_statistics as query_product_statistics,
)
from app.repositories.products import (
    get_top_refunded_products as query_top_refunded_products,
)
from app.repositories.refunds import get_recent_refunds as query_recent_refunds
from app.repositories.refunds import (
    get_refund_reason_breakdown as query_refund_reason_breakdown,
)
from mcp_servers.postgres_server._serialization import to_json_compatible
from mcp_servers.postgres_server._types import (
    CustomerOrderOutput,
    CustomerOrdersResult,
    ProductLookupOutput,
    ProductLookupResult,
    ProductStatisticsOutput,
    ProductStatisticsResult,
    RecentRefundsResult,
    RefundOutput,
    RefundReasonBreakdownResult,
    RefundReasonOutput,
    TopRefundedProductOutput,
    TopRefundedProductsResult,
)

ISO_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
REFUND_RATE_DEFINITION = (
    "distinct refunded order items divided by sold order items for non-cancelled "
    "orders in the selected order-date cohort; refunds must also be requested "
    "within the selected interval"
)
READ_ONLY_TOOL = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


@asynccontextmanager
async def lifespan(_: MCPServer[None]) -> AsyncIterator[None]:
    try:
        yield None
    finally:
        await engine.dispose()


mcp = MCPServer[None](
    name="operations-postgres",
    title="AI Operations PostgreSQL",
    description="Read-only structured operations data tools.",
    version="0.1.0",
    lifespan=lifespan,
)


def _parse_date(value: str, field_name: str) -> date:
    if not ISO_DATE_PATTERN.fullmatch(value):
        raise ToolError(f"{field_name} must use YYYY-MM-DD format")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ToolError(f"{field_name} must be a valid calendar date") from error


def _parse_optional_date(value: str | None, field_name: str) -> date | None:
    return _parse_date(value, field_name) if value is not None else None


def _validation_error(error: ValueError) -> ToolError:
    return ToolError(str(error))


@mcp.tool(annotations=READ_ONLY_TOOL, structured_output=True)
async def find_products(query: str, limit: int = 10) -> ProductLookupResult:
    """Find products by name so their IDs can be used in product-specific tools."""
    try:
        async with async_session_factory() as session:
            products = await query_find_products(session, query, limit)
    except ValueError as error:
        raise _validation_error(error) from error

    return {
        "products": cast(list[ProductLookupOutput], to_json_compatible(products))
    }


@mcp.tool(annotations=READ_ONLY_TOOL, structured_output=True)
async def get_customer_orders(
    customer_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
) -> CustomerOrdersResult:
    """Return one customer's orders, newest first, with optional UTC date bounds."""
    try:
        async with async_session_factory() as session:
            orders = await query_customer_orders(
                session,
                customer_id,
                _parse_optional_date(start_date, "start_date"),
                _parse_optional_date(end_date, "end_date"),
                limit,
            )
    except ValueError as error:
        raise _validation_error(error) from error

    return {
        "orders": cast(list[CustomerOrderOutput], to_json_compatible(orders))
    }


@mcp.tool(annotations=READ_ONLY_TOOL, structured_output=True)
async def get_recent_refunds(
    start_date: str,
    end_date: str,
    limit: int = 100,
) -> RecentRefundsResult:
    """Return refunds requested in a UTC date range with product and order context."""
    try:
        async with async_session_factory() as session:
            refunds = await query_recent_refunds(
                session,
                _parse_date(start_date, "start_date"),
                _parse_date(end_date, "end_date"),
                limit,
            )
    except ValueError as error:
        raise _validation_error(error) from error

    return {"refunds": cast(list[RefundOutput], to_json_compatible(refunds))}


@mcp.tool(annotations=READ_ONLY_TOOL, structured_output=True)
async def get_top_refunded_products(
    start_date: str,
    end_date: str,
    limit: int = 5,
    min_sold_items: int = 20,
) -> TopRefundedProductsResult:
    """Rank products highest refund rate first; returns IDs and rank 1 is worst-performing."""
    try:
        async with async_session_factory() as session:
            products = await query_top_refunded_products(
                session,
                _parse_date(start_date, "start_date"),
                _parse_date(end_date, "end_date"),
                limit,
                min_sold_items,
            )
    except ValueError as error:
        raise _validation_error(error) from error

    serialized_products = cast(list[dict[str, object]], to_json_compatible(products))
    ranked_products = cast(
        list[TopRefundedProductOutput],
        [
            {"rank": rank, **product}
            for rank, product in enumerate(serialized_products, start=1)
        ],
    )
    return {
        "products": ranked_products,
        "refund_rate_definition": REFUND_RATE_DEFINITION,
    }


@mcp.tool(annotations=READ_ONLY_TOOL, structured_output=True)
async def get_product_statistics(
    product_id: int,
    start_date: str,
    end_date: str,
) -> ProductStatisticsResult:
    """Return sales and refund statistics for one product over a UTC date range."""
    try:
        async with async_session_factory() as session:
            statistics = await query_product_statistics(
                session,
                product_id,
                _parse_date(start_date, "start_date"),
                _parse_date(end_date, "end_date"),
            )
    except ValueError as error:
        raise _validation_error(error) from error

    if statistics is None:
        return {"found": False, "product": None}
    return {
        "found": True,
        "product": cast(ProductStatisticsOutput, to_json_compatible(statistics)),
    }


@mcp.tool(annotations=READ_ONLY_TOOL, structured_output=True)
async def get_refund_reason_breakdown(
    start_date: str,
    end_date: str,
    product_id: int | None = None,
) -> RefundReasonBreakdownResult:
    """Count refund reasons for one product ID, or all products when product_id is omitted."""
    try:
        async with async_session_factory() as session:
            reasons = await query_refund_reason_breakdown(
                session,
                _parse_date(start_date, "start_date"),
                _parse_date(end_date, "end_date"),
                product_id,
            )
    except ValueError as error:
        raise _validation_error(error) from error

    return {
        "reasons": cast(list[RefundReasonOutput], to_json_compatible(reasons))
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
