from datetime import datetime
from decimal import Decimal

from sqlalchemy import Numeric, cast, distinct, func, select
from sqlalchemy.sql.selectable import Subquery

from app.models import Order, OrderItem, OrderStatus, Product, Refund


def build_product_metrics_subquery(
    start_at: datetime, end_at: datetime
) -> Subquery:
    sold = (
        select(
            OrderItem.product_id.label("product_id"),
            func.sum(OrderItem.quantity).label("units_sold"),
            func.count(OrderItem.id).label("sold_order_items"),
            func.sum(OrderItem.quantity * OrderItem.unit_price).label("gross_sales"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.ordered_at >= start_at,
            Order.ordered_at < end_at,
            Order.status != OrderStatus.CANCELLED,
        )
        .group_by(OrderItem.product_id)
        .subquery("sold_products")
    )

    refunded = (
        select(
            OrderItem.product_id.label("product_id"),
            func.count(distinct(OrderItem.id)).label("refunded_order_items"),
            func.count(Refund.id).label("refund_count"),
            func.sum(Refund.amount).label("refund_amount"),
        )
        .join(Refund, Refund.order_item_id == OrderItem.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.ordered_at >= start_at,
            Order.ordered_at < end_at,
            Order.status != OrderStatus.CANCELLED,
            Refund.requested_at >= start_at,
            Refund.requested_at < end_at,
        )
        .group_by(OrderItem.product_id)
        .subquery("refunded_products")
    )

    units_sold = func.coalesce(sold.c.units_sold, 0)
    sold_order_items = func.coalesce(sold.c.sold_order_items, 0)
    refunded_order_items = func.coalesce(refunded.c.refunded_order_items, 0)
    refund_count = func.coalesce(refunded.c.refund_count, 0)
    gross_sales = func.coalesce(sold.c.gross_sales, Decimal("0.00"))
    refund_amount = func.coalesce(refunded.c.refund_amount, Decimal("0.00"))
    refund_rate = func.coalesce(
        cast(refunded_order_items, Numeric(20, 10))
        / func.nullif(sold_order_items, 0),
        Decimal("0"),
    )

    return (
        select(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            units_sold.label("units_sold"),
            sold_order_items.label("sold_order_items"),
            refunded_order_items.label("refunded_order_items"),
            refund_count.label("refund_count"),
            gross_sales.label("gross_sales"),
            refund_amount.label("refund_amount"),
            refund_rate.label("refund_rate"),
        )
        .outerjoin(sold, sold.c.product_id == Product.id)
        .outerjoin(refunded, refunded.c.product_id == Product.id)
        .subquery("product_metrics")
    )
