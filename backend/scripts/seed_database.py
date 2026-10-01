import argparse
import asyncio

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.engine import engine
from app.database.session import async_session_factory
from app.models import Customer, Order, OrderItem, Product, Refund
from app.seed.generator import (
    DATASET_REFERENCE_DATE,
    RANDOM_SEED,
    GeneratedSeedData,
    generate_seed_data,
    summarize_product_patterns,
)

EXPECTED_SCHEMA_REVISION = "20261001_0001"


class SeedSafetyError(RuntimeError):
    pass


async def _verify_schema_revision(session: AsyncSession) -> None:
    revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
    if revision != EXPECTED_SCHEMA_REVISION:
        raise SeedSafetyError(
            f"database schema must be at Alembic revision {EXPECTED_SCHEMA_REVISION}; "
            f"found {revision!r}"
        )


async def _application_row_counts(session: AsyncSession) -> dict[str, int]:
    return {
        "customers": int(
            await session.scalar(select(func.count()).select_from(Customer)) or 0
        ),
        "products": int(
            await session.scalar(select(func.count()).select_from(Product)) or 0
        ),
        "orders": int(await session.scalar(select(func.count()).select_from(Order)) or 0),
        "order_items": int(
            await session.scalar(select(func.count()).select_from(OrderItem)) or 0
        ),
        "refunds": int(await session.scalar(select(func.count()).select_from(Refund)) or 0),
    }


async def _clear_application_tables(session: AsyncSession) -> None:
    for model in (Refund, OrderItem, Order, Product, Customer):
        await session.execute(delete(model))


async def _insert_seed_data(session: AsyncSession, data: GeneratedSeedData) -> None:
    customers = [
        Customer(name=row.name, email=row.email, created_at=row.created_at)
        for row in data.customers
    ]
    products = [
        Product(
            name=row.name,
            category=row.category,
            price=row.price,
            created_at=row.created_at,
        )
        for row in data.products
    ]
    session.add_all(customers)
    session.add_all(products)
    await session.flush()

    products_by_key = {
        seed.key: product for seed, product in zip(data.products, products, strict=True)
    }
    orders: list[Order] = []
    for row in data.orders:
        order = Order(
            customer_id=customers[row.customer_index].id,
            status=row.status,
            ordered_at=row.ordered_at,
            total_amount=row.total_amount,
        )
        for item_row in row.items:
            item = OrderItem(
                product_id=products_by_key[item_row.product_key].id,
                quantity=item_row.quantity,
                unit_price=item_row.unit_price,
            )
            if item_row.refund is not None:
                item.refunds.append(
                    Refund(
                        reason=item_row.refund.reason,
                        amount=item_row.refund.amount,
                        status=item_row.refund.status,
                        requested_at=item_row.refund.requested_at,
                        processed_at=item_row.refund.processed_at,
                    )
                )
            order.items.append(item)
        orders.append(order)

    session.add_all(orders)
    await session.flush()


def _print_summary(data: GeneratedSeedData) -> None:
    print(f"Random seed: {RANDOM_SEED}")
    print(f"Reference date: {DATASET_REFERENCE_DATE.date().isoformat()}")
    print(f"Customers: {len(data.customers)}")
    print(f"Products: {len(data.products)}")
    print(f"Orders: {len(data.orders)}")
    print(f"Order items: {data.order_item_count}")
    print(f"Refunds: {data.refund_count}")
    print("Pattern products:")
    for summary in summarize_product_patterns(data):
        reason = summary.most_common_reason.value if summary.most_common_reason else "none"
        print(
            f"  {summary.product_name}: units sold={summary.units_sold}, "
            f"refunded units={summary.refunded_units}, "
            f"refunded order-items={summary.refunded_order_items}, "
            f"refund rate={summary.refund_rate}%, top reason={reason}"
        )


async def seed_database(*, reset: bool) -> GeneratedSeedData:
    data = generate_seed_data()
    async with async_session_factory() as session:
        async with session.begin():
            await _verify_schema_revision(session)
            counts = await _application_row_counts(session)
            if any(counts.values()):
                if not reset:
                    populated = ", ".join(
                        f"{table}={count}" for table, count in counts.items() if count
                    )
                    raise SeedSafetyError(
                        "application tables are not empty "
                        f"({populated}); rerun with --reset to replace development data"
                    )
                await _clear_application_tables(session)
                print("Existing application rows removed because --reset was provided")

            await _insert_seed_data(session, data)

    _print_summary(data)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed deterministic development data")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete existing application rows before inserting the deterministic dataset",
    )
    args = parser.parse_args()

    async def run() -> None:
        try:
            await seed_database(reset=args.reset)
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
    except SeedSafetyError as error:
        parser.exit(status=1, message=f"Seed aborted: {error}\n")


if __name__ == "__main__":
    main()
