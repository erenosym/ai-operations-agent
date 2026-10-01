from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.database.engine import engine
from app.database.session import async_session_factory
from app.models import Customer, Order, OrderItem, Product, Refund, RefundReason
from app.repositories import (
    find_products,
    get_customer_orders,
    get_product_statistics,
    get_recent_refunds,
    get_refund_reason_breakdown,
    get_top_refunded_products,
)
from app.seed.generator import (
    HIGH_REFUND_PRODUCT,
    LOW_REFUND_PRODUCT,
    SIZE_REFUND_PRODUCT,
)

pytestmark = pytest.mark.integration

START_DATE = date(2026, 4, 1)
END_DATE = date(2026, 10, 1)


async def _run_repository_assertions() -> None:
    async with async_session_factory() as session:
        exact_lookup = await find_products(session, "StridePro Running Shoes")
        assert exact_lookup
        assert exact_lookup[0].name == "StridePro Running Shoes"
        assert isinstance(exact_lookup[0].price, Decimal)

        for query, expected_name in (
            ("StridePro", "StridePro Running Shoes"),
            ("Wireless Headphones", "Pulse Wireless Headphones"),
            ("Keyboard", "Forge Mechanical Keyboard"),
        ):
            matches = await find_products(session, query)
            assert matches
            assert any(match.name == expected_name for match in matches)

        assert await find_products(session, "no-such-catalog-product") == []

        products = {
            name: product_id
            for product_id, name in (
                await session.execute(
                    select(Product.id, Product.name).where(
                        Product.name.in_(
                            [
                                HIGH_REFUND_PRODUCT,
                                SIZE_REFUND_PRODUCT,
                                LOW_REFUND_PRODUCT,
                            ]
                        )
                    )
                )
            ).all()
        }
        assert set(products) == {
            HIGH_REFUND_PRODUCT,
            SIZE_REFUND_PRODUCT,
            LOW_REFUND_PRODUCT,
        }

        top_products = await get_top_refunded_products(
            session,
            START_DATE,
            END_DATE,
            limit=50,
            min_order_items_sold=20,
        )
        positions = {
            result.product_name: index for index, result in enumerate(top_products, start=1)
        }
        by_name = {result.product_name: result for result in top_products}
        assert positions[HIGH_REFUND_PRODUCT] <= 2
        assert positions[SIZE_REFUND_PRODUCT] <= 3
        assert (
            by_name[HIGH_REFUND_PRODUCT].refund_rate
            > by_name[LOW_REFUND_PRODUCT].refund_rate * 5
        )

        headphones = await get_product_statistics(
            session, products[HIGH_REFUND_PRODUCT], START_DATE, END_DATE
        )
        shoes = await get_product_statistics(
            session, products[SIZE_REFUND_PRODUCT], START_DATE, END_DATE
        )
        keyboard = await get_product_statistics(
            session, products[LOW_REFUND_PRODUCT], START_DATE, END_DATE
        )
        assert headphones is not None and headphones.refund_rate > Decimal("0.25")
        assert shoes is not None
        assert shoes.most_common_refund_reason == RefundReason.SIZE_ISSUE
        assert keyboard is not None and keyboard.refund_rate < Decimal("0.06")

        reason_breakdown = await get_refund_reason_breakdown(
            session,
            START_DATE,
            END_DATE,
            product_id=products[SIZE_REFUND_PRODUCT],
        )
        assert reason_breakdown[0].reason == RefundReason.SIZE_ISSUE
        assert abs(
            sum((row.percentage for row in reason_breakdown), Decimal("0"))
            - Decimal("1")
        ) < Decimal("1e-25")

        customer_id = await session.scalar(
            select(Customer.id)
            .join(Order, Order.customer_id == Customer.id)
            .group_by(Customer.id)
            .having(func.count(Order.id) >= 2)
            .order_by(Customer.id)
            .limit(1)
        )
        assert customer_id is not None
        customer_orders = await get_customer_orders(
            session, customer_id, START_DATE, END_DATE, limit=100
        )
        assert len(customer_orders) >= 2
        assert all(order.customer_id == customer_id for order in customer_orders)
        assert customer_orders == sorted(
            customer_orders,
            key=lambda order: (order.ordered_at, order.order_id),
            reverse=True,
        )
        newest_date = customer_orders[0].ordered_at.date()
        same_day_orders = await get_customer_orders(
            session, customer_id, newest_date, newest_date, limit=100
        )
        assert same_day_orders
        assert all(order.ordered_at.date() == newest_date for order in same_day_orders)

        recent_refunds = await get_recent_refunds(
            session, date(2026, 9, 1), END_DATE, limit=100
        )
        assert recent_refunds
        assert all(
            date(2026, 9, 1) <= refund.requested_at.date() <= END_DATE
            for refund in recent_refunds
        )
        assert all(
            refund.product_id > 0 and refund.order_id > 0 and refund.customer_id > 0
            for refund in recent_refunds
        )
        first_refund = recent_refunds[0]
        joined_values = (
            await session.execute(
                select(Product.name, Order.id, Order.customer_id)
                .select_from(Refund)
                .join(OrderItem, OrderItem.id == Refund.order_item_id)
                .join(Product, Product.id == OrderItem.product_id)
                .join(Order, Order.id == OrderItem.order_id)
                .where(Refund.id == first_refund.refund_id)
            )
        ).one()
        assert joined_values == (
            first_refund.product_name,
            first_refund.order_id,
            first_refund.customer_id,
        )

        missing_product = await get_product_statistics(
            session, max(products.values()) + 1_000_000, START_DATE, END_DATE
        )
        assert missing_product is None


def test_seeded_repository_queries() -> None:
    import asyncio

    async def run() -> None:
        try:
            await _run_repository_assertions()
        finally:
            await engine.dispose()

    asyncio.run(run())
