from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import RefundReasonCount, RefundSummary
from app.models import Order, OrderItem, Product, Refund
from app.repositories._math import decimal_ratio
from app.repositories._validation import date_range_utc, validate_limit

MAX_RECENT_REFUNDS_LIMIT = 500


async def get_recent_refunds(
    session: AsyncSession,
    start_date: date,
    end_date: date,
    limit: int = 100,
) -> list[RefundSummary]:
    validate_limit(limit, maximum=MAX_RECENT_REFUNDS_LIMIT)
    start_at, end_at = date_range_utc(start_date, end_date)

    statement = (
        select(
            Refund.id.label("refund_id"),
            Refund.requested_at,
            Refund.status,
            Refund.reason,
            Refund.amount,
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            Order.id.label("order_id"),
            Order.customer_id,
        )
        .join(OrderItem, OrderItem.id == Refund.order_item_id)
        .join(Product, Product.id == OrderItem.product_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Refund.requested_at >= start_at, Refund.requested_at < end_at)
        .order_by(Refund.requested_at.desc(), Refund.id.desc())
        .limit(limit)
    )
    rows = (await session.execute(statement)).mappings().all()
    return [
        RefundSummary(
            refund_id=row["refund_id"],
            requested_at=row["requested_at"],
            status=row["status"],
            reason=row["reason"],
            amount=Decimal(row["amount"]),
            product_id=row["product_id"],
            product_name=row["product_name"],
            order_id=row["order_id"],
            customer_id=row["customer_id"],
        )
        for row in rows
    ]


async def get_refund_reason_breakdown(
    session: AsyncSession,
    start_date: date,
    end_date: date,
    product_id: int | None = None,
) -> list[RefundReasonCount]:
    start_at, end_at = date_range_utc(start_date, end_date)
    statement = (
        select(Refund.reason, func.count(Refund.id).label("count"))
        .where(Refund.requested_at >= start_at, Refund.requested_at < end_at)
        .group_by(Refund.reason)
        .order_by(func.count(Refund.id).desc(), Refund.reason.asc())
    )
    if product_id is not None:
        statement = statement.join(
            OrderItem, OrderItem.id == Refund.order_item_id
        ).where(OrderItem.product_id == product_id)

    rows = (await session.execute(statement)).mappings().all()
    total = sum(row["count"] for row in rows)
    if total == 0:
        return []

    return [
        RefundReasonCount(
            reason=row["reason"],
            count=row["count"],
            percentage=decimal_ratio(row["count"], total),
        )
        for row in rows
    ]
