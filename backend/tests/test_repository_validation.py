import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.repositories._math import decimal_ratio
from app.repositories.products import find_products
from app.repositories._validation import (
    date_range_utc,
    optional_date_range_utc,
    validate_limit,
    validate_minimum,
)


def test_date_range_uses_inclusive_start_and_exclusive_end() -> None:
    start_at, end_at = date_range_utc(date(2026, 9, 1), date(2026, 9, 30))

    assert start_at == datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert end_at == datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_date_range_rejects_reversed_dates() -> None:
    with pytest.raises(ValueError, match="start_date"):
        date_range_utc(date(2026, 10, 1), date(2026, 9, 30))


def test_optional_date_range_accepts_one_sided_bounds() -> None:
    start_at, end_at = optional_date_range_utc(date(2026, 9, 1), None)
    assert start_at == datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert end_at is None

    start_at, end_at = optional_date_range_utc(None, date(2026, 9, 30))
    assert start_at is None
    assert end_at == datetime(2026, 10, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_limit_validation_rejects_unsafe_values(limit: int) -> None:
    with pytest.raises(ValueError, match="limit"):
        validate_limit(limit, maximum=100)


def test_minimum_and_decimal_ratio_behavior() -> None:
    validate_minimum(1, name="minimum")
    with pytest.raises(ValueError, match="minimum"):
        validate_minimum(0, name="minimum")

    assert decimal_ratio(1, 4) == Decimal("0.25")
    assert decimal_ratio(0, 0) == Decimal("0")
    with pytest.raises(ValueError, match="negative"):
        decimal_ratio(-1, 4)


@pytest.mark.parametrize(
    ("query", "limit"),
    [("", 10), ("   ", 10), ("product", 0), ("product", 26)],
)
def test_product_lookup_rejects_invalid_query_and_limit(
    query: str, limit: int
) -> None:
    session = AsyncMock()
    with pytest.raises(ValueError):
        asyncio.run(find_products(session, query, limit))
    session.execute.assert_not_awaited()
