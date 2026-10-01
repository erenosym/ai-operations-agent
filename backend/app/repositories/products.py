from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import ProductLookupResult, ProductStatistics, TopRefundedProduct
from app.models import Order, OrderItem, OrderStatus, Product, Refund
from app.repositories._product_metrics import build_product_metrics_subquery
from app.repositories._validation import (
    date_range_utc,
    validate_limit,
    validate_minimum,
)

MAX_TOP_PRODUCTS_LIMIT = 50
MAX_PRODUCT_LOOKUP_LIMIT = 25


async def find_products(
    session: AsyncSession,
    query: str,
    limit: int = 10,
) -> list[ProductLookupResult]:
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must not be empty")
    validate_limit(limit, maximum=MAX_PRODUCT_LOOKUP_LIMIT)

    escaped_query = (
        normalized_query.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    partial_pattern = f"%{escaped_query}%"
    exact_match_rank = case(
        (func.lower(Product.name) == normalized_query.lower(), 0),
        else_=1,
    )
    rows = (
        await session.execute(
            select(Product.id, Product.name, Product.category, Product.price)
            .where(
                or_(
                    Product.name.ilike(partial_pattern, escape="\\"),
                    Product.category.ilike(partial_pattern, escape="\\"),
                )
            )
            .order_by(
                exact_match_rank.asc(),
                func.lower(Product.name).asc(),
                Product.id.asc(),
            )
            .limit(limit)
        )
    ).all()
    return [
        ProductLookupResult(
            product_id=row.id,
            name=row.name,
            category=row.category,
            price=Decimal(row.price),
        )
        for row in rows
    ]


async def get_top_refunded_products(
    session: AsyncSession,
    start_date: date,
    end_date: date,
    limit: int = 5,
    min_order_items_sold: int = 20,
) -> list[TopRefundedProduct]:
    validate_limit(limit, maximum=MAX_TOP_PRODUCTS_LIMIT)
    validate_minimum(min_order_items_sold, name="min_order_items_sold")
    start_at, end_at = date_range_utc(start_date, end_date)
    metrics = build_product_metrics_subquery(start_at, end_at)

    statement = (
        select(metrics)
        .where(metrics.c.sold_order_items >= min_order_items_sold)
        .order_by(
            metrics.c.refund_rate.desc(),
            metrics.c.refunded_order_items.desc(),
            metrics.c.product_id.asc(),
        )
        .limit(limit)
    )
    rows = (await session.execute(statement)).mappings().all()
    return [_top_product_from_row(row) for row in rows]


async def get_product_statistics(
    session: AsyncSession,
    product_id: int,
    start_date: date,
    end_date: date,
) -> ProductStatistics | None:
    start_at, end_at = date_range_utc(start_date, end_date)
    metrics = build_product_metrics_subquery(start_at, end_at)
    row = (
        await session.execute(
            select(metrics).where(metrics.c.product_id == product_id)
        )
    ).mappings().one_or_none()
    if row is None:
        return None

    reason_row = (
        await session.execute(
            select(Refund.reason, func.count(Refund.id).label("count"))
            .join(OrderItem, OrderItem.id == Refund.order_item_id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                OrderItem.product_id == product_id,
                Order.ordered_at >= start_at,
                Order.ordered_at < end_at,
                Order.status != OrderStatus.CANCELLED,
                Refund.requested_at >= start_at,
                Refund.requested_at < end_at,
            )
            .group_by(Refund.reason)
            .order_by(func.count(Refund.id).desc(), Refund.reason.asc())
            .limit(1)
        )
    ).mappings().one_or_none()

    return ProductStatistics(
        product_id=row["product_id"],
        product_name=row["product_name"],
        units_sold=row["units_sold"],
        sold_order_items=row["sold_order_items"],
        refunded_order_items=row["refunded_order_items"],
        refund_count=row["refund_count"],
        gross_sales=Decimal(row["gross_sales"]),
        refund_amount=Decimal(row["refund_amount"]),
        refund_rate=Decimal(row["refund_rate"]),
        most_common_refund_reason=(reason_row["reason"] if reason_row else None),
    )


def _top_product_from_row(row: Mapping[str, Any]) -> TopRefundedProduct:
    return TopRefundedProduct(
        product_id=row["product_id"],
        product_name=row["product_name"],
        units_sold=row["units_sold"],
        sold_order_items=row["sold_order_items"],
        refunded_order_items=row["refunded_order_items"],
        refund_count=row["refund_count"],
        gross_sales=Decimal(row["gross_sales"]),
        refund_amount=Decimal(row["refund_amount"]),
        refund_rate=Decimal(row["refund_rate"]),
    )
