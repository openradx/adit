from datetime import time


def in_time_slot(start_time: time, end_time: time, check_time: time) -> bool:
    """Checks if the current time is in a time range."""
    if start_time < end_time:
        return check_time >= start_time and check_time <= end_time
    else:  # crosses midnight
        return check_time >= start_time or check_time <= end_time
