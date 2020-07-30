from datetime import datetime, timedelta
from django.utils import timezone
from ..models import AppSettings


def is_time_between(begin_time, end_time, check_time):
    """Checks if a given time is between two other times.

    If the time to check is not provided then use the current time.
    Adapted from https://stackoverflow.com/a/10048290/166229
    """
    # pylint: disable=no-else-return, chained-comparison
    if begin_time < end_time:
        return check_time >= begin_time and check_time <= end_time
    else:  # crosses midnight
        return check_time >= begin_time or check_time <= end_time


def must_be_scheduled():
    """Checks if the batch job can run now or must be scheduled.

    In the dynamic site settings a time slot is specified when the
    batch transfer jobs should run. The job processing could also be
    suspended in the settings.
    """
    app_settings = AppSettings.load()
    suspended = app_settings.batch_transfer_suspended
    begin_time = app_settings.batch_slot_begin_time
    end_time = app_settings.batch_slot_end_time
    check_time = timezone.now().time()
    return suspended or not is_time_between(begin_time, end_time, check_time)


def next_batch_slot():
    """Return the next datetime slot when a batch job can be processed."""
    app_settings = AppSettings.load()
    begin_time = app_settings.batch_slot_begin_time
    now = timezone.now()

    if now.time() < begin_time:
        return datetime.combine(now.date(), begin_time)

    tomorrow = now.date() + timedelta(days=1)
    return datetime.combine(tomorrow, begin_time)
