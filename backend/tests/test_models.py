from sqlalchemy import CheckConstraint, DateTime, Float, Numeric, UniqueConstraint

from app.database.base import Base
from app.models import Customer, Order, OrderItem, Product, Refund


def test_metadata_contains_expected_tables_and_constraints() -> None:
    assert set(Base.metadata.tables) == {
        "customers",
        "products",
        "orders",
        "order_items",
        "refunds",
    }

    customer_constraints = Customer.__table__.constraints
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"email"}
        for constraint in customer_constraints
    )

    expected_checks = {
        "ck_products_price_non_negative",
        "ck_orders_total_amount_non_negative",
        "ck_order_items_quantity_positive",
        "ck_order_items_unit_price_non_negative",
        "ck_refunds_amount_positive",
    }
    actual_checks = {
        constraint.name
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert expected_checks <= actual_checks


def test_money_and_timestamp_columns_use_safe_types() -> None:
    money_columns = [
        Product.__table__.c.price,
        Order.__table__.c.total_amount,
        OrderItem.__table__.c.unit_price,
        Refund.__table__.c.amount,
    ]
    assert all(isinstance(column.type, Numeric) for column in money_columns)
    assert not any(isinstance(column.type, Float) for column in money_columns)

    timestamp_columns = [
        Customer.__table__.c.created_at,
        Product.__table__.c.created_at,
        Order.__table__.c.ordered_at,
        Refund.__table__.c.requested_at,
        Refund.__table__.c.processed_at,
    ]
    assert all(
        isinstance(column.type, DateTime) and column.type.timezone
        for column in timestamp_columns
    )


def test_relationships_and_delete_policies_are_mapped() -> None:
    assert set(Customer.__mapper__.relationships.keys()) == {"orders"}
    assert set(Order.__mapper__.relationships.keys()) == {"customer", "items"}
    assert set(Product.__mapper__.relationships.keys()) == {"order_items"}
    assert set(OrderItem.__mapper__.relationships.keys()) == {
        "order",
        "product",
        "refunds",
    }
    assert set(Refund.__mapper__.relationships.keys()) == {"order_item"}
    assert Customer.orders.property.passive_deletes == "all"
    assert Product.order_items.property.passive_deletes == "all"
    assert Order.items.property.passive_deletes == "all"
    assert OrderItem.refunds.property.passive_deletes == "all"

    foreign_keys = {
        foreign_key
        for table in Base.metadata.tables.values()
        for foreign_key in table.foreign_keys
    }
    assert len(foreign_keys) == 4
    assert all(foreign_key.ondelete == "RESTRICT" for foreign_key in foreign_keys)
