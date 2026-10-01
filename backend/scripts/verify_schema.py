import asyncio
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from app.database.engine import engine
from app.models import Customer, Order, OrderItem, Product, Refund


async def expect_constraint_failure(connection, statement, label: str) -> None:
    savepoint = await connection.begin_nested()
    try:
        await connection.execute(statement)
    except IntegrityError:
        await savepoint.rollback()
        print(f"Constraint check passed: {label}")
    else:
        await savepoint.rollback()
        raise AssertionError(f"Expected database constraint failure: {label}")


async def verify_schema() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            customer_id = await connection.scalar(
                insert(Customer)
                .values(name="Schema Check", email=f"schema-{uuid4()}@example.com")
                .returning(Customer.id)
            )
            product_id = await connection.scalar(
                insert(Product)
                .values(name="Valid Product", category="verification", price=Decimal("25.00"))
                .returning(Product.id)
            )
            second_product_id = await connection.scalar(
                insert(Product)
                .values(name="Second Product", category="verification", price=Decimal("10.00"))
                .returning(Product.id)
            )
            order_id = await connection.scalar(
                insert(Order)
                .values(customer_id=customer_id, status="paid", total_amount=Decimal("25.00"))
                .returning(Order.id)
            )
            order_item_id = await connection.scalar(
                insert(OrderItem)
                .values(
                    order_id=order_id,
                    product_id=product_id,
                    quantity=1,
                    unit_price=Decimal("25.00"),
                )
                .returning(OrderItem.id)
            )
            refund_id = await connection.scalar(
                insert(Refund)
                .values(
                    order_item_id=order_item_id,
                    reason="defective",
                    amount=Decimal("25.00"),
                    status="requested",
                )
                .returning(Refund.id)
            )

            assert all(
                identifier is not None
                for identifier in (
                    customer_id,
                    product_id,
                    order_id,
                    order_item_id,
                    refund_id,
                )
            )
            print("Valid relational insert passed: customer -> order -> product -> item -> refund")

            await expect_constraint_failure(
                connection,
                insert(Product).values(
                    name="Invalid Product",
                    category="verification",
                    price=Decimal("-1.00"),
                ),
                "negative product price",
            )
            await expect_constraint_failure(
                connection,
                insert(OrderItem).values(
                    order_id=order_id,
                    product_id=second_product_id,
                    quantity=0,
                    unit_price=Decimal("10.00"),
                ),
                "zero order-item quantity",
            )
            await expect_constraint_failure(
                connection,
                insert(Refund).values(
                    order_item_id=order_item_id,
                    reason="other",
                    amount=Decimal("0.00"),
                    status="requested",
                ),
                "zero refund amount",
            )
        finally:
            await transaction.rollback()

    print("Verification transaction rolled back; no test rows retained")


async def main() -> None:
    try:
        await verify_schema()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
