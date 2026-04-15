from datetime import date

from adit.mass_transfer.utils.partitions import build_partitions


def test_build_partitions_daily():
    windows = build_partitions(date(2024, 1, 1), date(2024, 1, 3), "daily")

    assert len(windows) == 3
    assert [window.key for window in windows] == ["20240101", "20240102", "20240103"]
    assert windows[0].start.hour == 0
    assert windows[0].start.minute == 0
    assert windows[0].end.hour == 23
    assert windows[0].end.minute == 59
    assert windows[0].end.second == 59


def test_build_partitions_weekly():
    windows = build_partitions(date(2024, 1, 1), date(2024, 1, 10), "weekly")

    assert len(windows) == 2
    assert [window.key for window in windows] == ["20240101-20240107", "20240108-20240110"]
    assert windows[0].start.date() == date(2024, 1, 1)
    assert windows[0].end.date() == date(2024, 1, 7)
    assert windows[1].start.date() == date(2024, 1, 8)
    assert windows[1].end.date() == date(2024, 1, 10)
