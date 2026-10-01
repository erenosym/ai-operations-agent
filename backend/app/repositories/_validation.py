from datetime import date, datetime, time, timedelta, timezone


def date_range_utc(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    """Return an inclusive-start, exclusive-end UTC interval for whole dates."""
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")

    start_at = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_at = datetime.combine(
        end_date + timedelta(days=1), time.min, tzinfo=timezone.utc
    )
    return start_at, end_at


def optional_date_range_utc(
    start_date: date | None, end_date: date | None
) -> tuple[datetime | None, datetime | None]:
    if start_date is not None and end_date is not None:
        return date_range_utc(start_date, end_date)

    start_at = (
        datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        if start_date is not None
        else None
    )
    end_at = (
        datetime.combine(
            end_date + timedelta(days=1), time.min, tzinfo=timezone.utc
        )
        if end_date is not None
        else None
    )
    return start_at, end_at


def validate_limit(limit: int, *, maximum: int) -> None:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    if limit > maximum:
        raise ValueError(f"limit must not exceed {maximum}")


def validate_minimum(value: int, *, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
