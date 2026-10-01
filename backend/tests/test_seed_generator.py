from decimal import Decimal

import pytest

from app.models import OrderStatus, RefundReason, RefundStatus
from app.seed.generator import (
    DATASET_REFERENCE_DATE,
    HIGH_REFUND_PRODUCT,
    LOW_REFUND_PRODUCT,
    SIZE_REFUND_PRODUCT,
    GeneratedSeedData,
    generate_seed_data,
    summarize_product_patterns,
)


@pytest.fixture(scope="module")
def seed_data() -> GeneratedSeedData:
    return generate_seed_data()


def test_generation_is_deterministic(seed_data: GeneratedSeedData) -> None:
    assert generate_seed_data() == seed_data
    assert len(seed_data.customers) == 500
    assert len(seed_data.products) == 50
    assert len(seed_data.orders) == 2_000
    assert seed_data.order_item_count == 5_877
    assert seed_data.refund_count == 404


def test_intentional_product_patterns_are_visible(
    seed_data: GeneratedSeedData,
) -> None:
    summaries = {
        summary.product_name: summary
        for summary in summarize_product_patterns(seed_data)
    }

    assert summaries[HIGH_REFUND_PRODUCT].refund_rate > Decimal("25")
    assert summaries[HIGH_REFUND_PRODUCT].most_common_reason == RefundReason.DEFECTIVE
    assert summaries[SIZE_REFUND_PRODUCT].refund_rate > Decimal("20")
    assert summaries[SIZE_REFUND_PRODUCT].most_common_reason == RefundReason.SIZE_ISSUE
    assert summaries[LOW_REFUND_PRODUCT].refund_rate < Decimal("6")
    assert (
        summaries[HIGH_REFUND_PRODUCT].refund_rate
        > summaries[LOW_REFUND_PRODUCT].refund_rate * 5
    )


def test_financial_and_temporal_invariants(seed_data: GeneratedSeedData) -> None:
    assert all(isinstance(product.price, Decimal) for product in seed_data.products)

    recent_orders = 0
    recent_refunds = 0
    for order in seed_data.orders:
        expected_total = sum(
            (item.unit_price * item.quantity for item in order.items),
            start=Decimal("0.00"),
        )
        assert isinstance(order.total_amount, Decimal)
        assert order.total_amount == expected_total
        if (DATASET_REFERENCE_DATE - order.ordered_at).days < 30:
            recent_orders += 1

        for item in order.items:
            assert isinstance(item.unit_price, Decimal)
            if item.refund is None:
                continue

            refund = item.refund
            assert order.status == OrderStatus.DELIVERED
            assert isinstance(refund.amount, Decimal)
            assert Decimal("0.00") < refund.amount <= item.unit_price * item.quantity
            assert order.ordered_at <= refund.requested_at <= DATASET_REFERENCE_DATE
            if (DATASET_REFERENCE_DATE - refund.requested_at).days < 30:
                recent_refunds += 1

            if refund.status in {RefundStatus.PROCESSED, RefundStatus.REJECTED}:
                assert refund.processed_at is not None
                assert refund.requested_at <= refund.processed_at <= DATASET_REFERENCE_DATE
            else:
                assert refund.processed_at is None

    assert recent_orders >= 250
    assert recent_refunds >= 25
