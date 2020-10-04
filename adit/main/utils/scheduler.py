from datetime import datetime, timedelta
import pytz
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
    """A scheduler that defines a time slot as time range.

    Args:
        begin_time (time): The start time of the slot
        end_time (time): The end time of the slot
        tzname (str): The timezone of the provided times
    """

    def __init__(self, begin_time, end_time, tzname=None):
        self.begin_time = begin_time
        self.end_time = end_time
        self.tzname = tzname

    def must_be_scheduled(self):
        """Checks if the batch job can run now or must be scheduled.

        In the dynamic site settings a time slot is specified when the
        batch transfer jobs should run. If begin time and end time are the same
        then scheduling is turned off.
        """
        if self.begin_time == self.end_time:
            return False

        now = timezone.now()
        if self.tzname:
            tz = pytz.timezone(self.tzname)
            now = now.astimezone(tz)

        check_time = now.time()
        return not is_time_between(self.begin_time, self.end_time, check_time)

    def next_slot(self):
        """Return the next datetime slot.

        The returned datetime object has the default Django timezone set
        (which is different from SERVER_TIME_ZONE and mostly UTC).
        """
        now = timezone.now()
        tz = now.tzinfo
        if self.tzname:
            tz = pytz.timezone(self.tzname)
            now = now.astimezone(tz)

        if now.time() < self.begin_time:
            slot = datetime.combine(now.date(), self.begin_time)
            slot = tz.localize(slot)
            return slot.astimezone(timezone.get_default_timezone())

        tomorrow = now.date() + timedelta(days=1)
        slot = datetime.combine(tomorrow, self.begin_time)
        slot = tz.localize(slot)
        return slot.astimezone(timezone.get_default_timezone())
