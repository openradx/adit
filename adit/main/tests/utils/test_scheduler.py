from datetime import time, datetime
import time_machine
from django.test import TestCase
from django.utils import timezone
from ...utils.scheduler import Scheduler, is_time_between


class IsTimeBetweenTest(TestCase):
    def test_is_time_between(self):
        params = (
            (time(1, 0), time(3, 0), time(2, 0)),
            (time(1, 0), time(3, 0), time(1, 0)),
            (time(1, 0), time(3, 0), time(3, 0)),
            (time(23, 0), time(1, 0), time(0, 0)),
        )
        for param in params:
            self.assertEqual(is_time_between(param[0], param[1], param[2]), True)

    def test_is_time_not_between(self):
        params = (
            (time(1, 0), time(3, 0), time(0, 0)),
            (time(1, 0), time(3, 0), time(4, 0)),
            (time(23, 0), time(1, 0), time(22, 0)),
            (time(23, 0), time(1, 0), time(2, 0)),
        )
        for param in params:
            self.assertEqual(is_time_between(param[0], param[1], param[2]), False)


class SchedulerTest(TestCase):
    @time_machine.travel("2020-11-05 23:00")
    def test_must_not_be_sheduled_when_scheduling_is_turned_off(self):
        scheduler = Scheduler(time(0, 0), time(0, 0))
        self.assertFalse(scheduler.must_be_scheduled())

    @time_machine.travel("2020-11-05 23:00")
    def test_must_not_be_sheduled(self):
        scheduler = Scheduler(time(22, 0), time(6, 0))
        self.assertFalse(scheduler.must_be_scheduled())

    @time_machine.travel("2020-11-05 21:00")
    def test_must_be_sheduled_when_outside_slot(self):
        scheduler = Scheduler(time(22, 0), time(6, 0))
        self.assertTrue(scheduler.must_be_scheduled())

    @time_machine.travel("2020-07-05 21:00")
    def test_must_not_be_sheduled_with_tz(self):
        scheduler = Scheduler(time(22, 0), time(6, 0), "Europe/Berlin")
        self.assertFalse(scheduler.must_be_scheduled())

    @time_machine.travel("2020-07-05 19:00")
    def test_must_be_sheduled_when_outside_slot_with_tz(self):
        scheduler = Scheduler(time(22, 0), time(6, 0), "Europe/Berlin")
        self.assertTrue(scheduler.must_be_scheduled())

    @time_machine.travel("2020-11-05 11:00")
    def test_next_batch_slot_on_same_day(self):
        scheduler = Scheduler(time(22, 0), time(6, 0))
        next_slot = datetime(2020, 11, 5, 22, 0)
        next_slot = timezone.make_aware(next_slot)
        self.assertEqual(scheduler.next_slot(), next_slot)

    @time_machine.travel("2020-11-05 23:00")
    def test_next_batch_slot_on_next_day(self):
        scheduler = Scheduler(time(22, 0), time(6, 0))
        next_slot = datetime(2020, 11, 6, 22, 0)
        next_slot = timezone.make_aware(next_slot)
        self.assertEqual(scheduler.next_slot(), next_slot)

    @time_machine.travel("2020-07-05 11:00")
    def test_next_batch_slot_on_same_day_with_tz_without_dst(self):
        scheduler = Scheduler(time(22, 0), time(6, 0), "Europe/Berlin")
        next_slot = datetime(2020, 7, 5, 20, 0)
        next_slot = timezone.make_aware(next_slot)
        self.assertEqual(scheduler.next_slot(), next_slot)

    @time_machine.travel("2020-11-05 11:00")
    def test_next_batch_slot_on_same_day_with_tz_with_dst(self):
        scheduler = Scheduler(time(22, 0), time(6, 0), "Europe/Berlin")
        next_slot = datetime(2020, 11, 5, 21, 0)
        next_slot = timezone.make_aware(next_slot)
        self.assertEqual(scheduler.next_slot(), next_slot)

    @time_machine.travel("2020-07-05 23:00")
    def test_next_batch_slot_on_next_day_with_tz_without_dst(self):
        scheduler = Scheduler(time(22, 0), time(6, 0), "Europe/Berlin")
        next_slot = datetime(2020, 7, 6, 20, 0)
        next_slot = timezone.make_aware(next_slot)
        self.assertEqual(scheduler.next_slot(), next_slot)

    @time_machine.travel("2020-11-05 23:00")
    def test_next_batch_slot_on_next_day_with_tz_with_dst(self):
        scheduler = Scheduler(time(22, 0), time(6, 0), "Europe/Berlin")
        next_slot = datetime(2020, 11, 6, 21, 0)
        next_slot = timezone.make_aware(next_slot)
        self.assertEqual(scheduler.next_slot(), next_slot)
