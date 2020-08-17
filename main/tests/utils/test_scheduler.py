from datetime import time, datetime
import time_machine
from django.test import TestCase
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
    def test_must_not_be_sheduled(self):
        scheduler = Scheduler(time(22, 0), time(6, 0))
        self.assertFalse(scheduler.must_be_scheduled())

    @time_machine.travel("2020-11-05 23:00")
    def test_must_be_sheduled_when_suspended(self):
        scheduler = Scheduler(time(22, 0), time(6, 0), True)
        self.assertTrue(scheduler.must_be_scheduled())

    @time_machine.travel("2020-11-05 21:00")
    def test_must_be_sheduled_when_outside_slot(self):
        scheduler = Scheduler(time(22, 0), time(6, 0))
        self.assertTrue(scheduler.must_be_scheduled())

    @time_machine.travel("2020-11-05 11:00")
    def test_next_batch_slot_on_same_day(self):
        scheduler = Scheduler(time(22, 0), time(6, 0))
        next_slot = datetime(2020, 11, 5, 22, 0)
        self.assertEqual(scheduler.next_slot(), next_slot)

    @time_machine.travel("2020-11-05 23:00")
    def test_next_batch_slot_on_next_day(self):
        scheduler = Scheduler(time(22, 0), time(6, 0))
        next_slot = datetime(2020, 11, 6, 22, 0)
        self.assertEqual(scheduler.next_slot(), next_slot)
