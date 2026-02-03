from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.utils import timezone


@dataclass(frozen=True)
class PartitionWindow:
    start: datetime
    end: datetime
    key: str


def build_partitions(
    start_date: date,
    end_date: date,
    granularity: str,
) -> list[PartitionWindow]:
    if end_date < start_date:
        raise ValueError("End date must be on or after the start date.")

    if granularity not in {"daily", "weekly"}:
        raise ValueError(f"Invalid granularity: {granularity}")

    if granularity == "daily":
        step = timedelta(days=1)
    else:
        step = timedelta(days=7)

    tz = timezone.get_current_timezone()
    windows: list[PartitionWindow] = []

    current = start_date
    while current <= end_date:
        window_end_date = min(current + step - timedelta(days=1), end_date)

        start_dt = timezone.make_aware(datetime.combine(current, time(0, 0, 0)), tz)
        end_dt = timezone.make_aware(datetime.combine(window_end_date, time(23, 59, 59)), tz)

        if current == window_end_date:
            key = current.strftime("%Y%m%d")
        else:
            key = f"{current:%Y%m%d}-{window_end_date:%Y%m%d}"

        windows.append(PartitionWindow(start=start_dt, end=end_dt, key=key))
        current = window_end_date + timedelta(days=1)

    return windows
