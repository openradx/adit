import argparse
from datetime import time


def valid_time_range(value: str) -> tuple[time, time] | None:
    if not value:
        return None

    try:
        start, end = value.split("-")
        return (
            time.fromisoformat(start),
            time.fromisoformat(end),
        )
    except ValueError:
        raise argparse.ArgumentTypeError("Invalid time range.")
