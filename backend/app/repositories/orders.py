from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import CustomerOrderSummary
from app.models import Order, OrderItem
from app.repositories._validation import optional_date_range_utc, validate_limit

MAX_CUSTOMER_ORDERS_LIMIT = 100


async def get_customer_orders(
    session: AsyncSession,
    customer_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 50,
) -> list[CustomerOrderSummary]:
    validate_limit(limit, maximum=MAX_CUSTOMER_ORDERS_LIMIT)
    start_at, end_at = optional_date_range_utc(start_date, end_date)

    statement = (
        select(
            Order.id.label("order_id"),
            Order.customer_id,
            Order.status,
            Order.ordered_at,
            Order.total_amount,
            func.count(OrderItem.id).label("order_item_count"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units"),
        )
        .outerjoin(OrderItem, OrderItem.order_id == Order.id)
        .where(Order.customer_id == customer_id)
        .group_by(
            Order.id,
            Order.customer_id,
            Order.status,
            Order.ordered_at,
            Order.total_amount,
        )
        .order_by(Order.ordered_at.desc(), Order.id.desc())
        .limit(limit)
    )
    if start_at is not None:
        statement = statement.where(Order.ordered_at >= start_at)
    if end_at is not None:
        statement = statement.where(Order.ordered_at < end_at)

    rows = (await session.execute(statement)).mappings().all()
    return [
        CustomerOrderSummary(
            order_id=row["order_id"],
            customer_id=row["customer_id"],
            status=row["status"],
            ordered_at=row["ordered_at"],
            total_amount=Decimal(row["total_amount"]),
            order_item_count=row["order_item_count"],
            units=row["units"],
        )
        for row in rows
    ]
