from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class PeriodBucket:
    label: str
    start: date
    end: date


def week_start(value: datetime | date) -> date:
    current = value.date() if isinstance(value, datetime) else value
    return current - timedelta(days=current.weekday())


def month_start(value: datetime | date) -> date:
    current = value.date() if isinstance(value, datetime) else value
    return current.replace(day=1)


def bucket_key(value: datetime | None, granularity: str = "weekly") -> str | None:
    if value is None:
        return None
    if granularity == "weekly":
        return week_start(value).isoformat()
    if granularity == "monthly":
        return month_start(value).isoformat()
    raise ValueError(f"unsupported granularity: {granularity}")


def split_period(start: date, end: date, granularity: str = "weekly") -> list[PeriodBucket]:
    if end <= start:
        return []
    if granularity not in {"weekly", "monthly"}:
        raise ValueError(f"unsupported granularity: {granularity}")

    cursor = week_start(start) if granularity == "weekly" else month_start(start)
    buckets: list[PeriodBucket] = []
    while cursor < end:
        if granularity == "weekly":
            next_cursor = cursor + timedelta(days=7)
        else:
            if cursor.month == 12:
                next_cursor = cursor.replace(year=cursor.year + 1, month=1)
            else:
                next_cursor = cursor.replace(month=cursor.month + 1)
        bucket_start = max(cursor, start)
        bucket_end = min(next_cursor, end)
        if bucket_start < bucket_end:
            buckets.append(
                PeriodBucket(
                    label=cursor.isoformat(),
                    start=bucket_start,
                    end=bucket_end,
                )
            )
        cursor = next_cursor
    return buckets

