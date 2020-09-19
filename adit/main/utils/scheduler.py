from datetime import datetime, timedelta
from django.utils import timezone


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


class Scheduler:
    def __init__(self, begin_time, end_time):
        self.begin_time = begin_time
        self.end_time = end_time

    def must_be_scheduled(self):
        """Checks if the batch job can run now or must be scheduled.

        In the dynamic site settings a time slot is specified when the
        batch transfer jobs should run.
        """
        check_time = timezone.now().time()
        return not is_time_between(self.begin_time, self.end_time, check_time)

    def next_slot(self):
        """Return the next datetime slot when a batch job can be processed."""
        now = timezone.now()

        if now.time() < self.begin_time:
            return datetime.combine(now.date(), self.begin_time)

        tomorrow = now.date() + timedelta(days=1)
        return datetime.combine(tomorrow, self.begin_time)
