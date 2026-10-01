from decimal import Decimal


def decimal_ratio(numerator: int, denominator: int) -> Decimal:
    if denominator < 0 or numerator < 0:
        raise ValueError("ratio values must not be negative")
    if denominator == 0:
        return Decimal("0")
    return Decimal(numerator) / Decimal(denominator)
