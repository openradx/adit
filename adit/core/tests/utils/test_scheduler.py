from datetime import datetime, time
import pytest
import time_machine
from django.utils import timezone
from ...utils.scheduler import Scheduler, is_time_between


@pytest.mark.parametrize(
    "begin_time,end_time,check_time",
    [
        (time(1, 0), time(3, 0), time(2, 0)),
        (time(1, 0), time(3, 0), time(1, 0)),
        (time(1, 0), time(3, 0), time(3, 0)),
        (time(23, 0), time(1, 0), time(0, 0)),
    ],
)
def test_is_time_between(begin_time, end_time, check_time):
    assert is_time_between(begin_time, end_time, check_time)


@pytest.mark.parametrize(
    "begin_time,end_time,check_time",
    [
        (time(1, 0), time(3, 0), time(0, 0)),
        (time(1, 0), time(3, 0), time(4, 0)),
        (time(23, 0), time(1, 0), time(22, 0)),
        (time(23, 0), time(1, 0), time(2, 0)),
    ],
)
def test_is_time_not_between(begin_time, end_time, check_time):
    assert not is_time_between(begin_time, end_time, check_time)


@time_machine.travel("2020-11-05 23:00")
def test_must_not_be_sheduled_when_scheduling_is_turned_off():
    scheduler = Scheduler(time(0, 0), time(0, 0))
    assert not scheduler.must_be_scheduled()


@time_machine.travel("2020-11-05 23:00")
def test_must_not_be_sheduled():
    scheduler = Scheduler(time(22, 0), time(6, 0))
    assert not scheduler.must_be_scheduled()


@time_machine.travel("2020-11-05 21:00")
def test_must_be_sheduled_when_outside_slot():
    scheduler = Scheduler(time(22, 0), time(6, 0))
    assert scheduler.must_be_scheduled()


@time_machine.travel("2020-11-05 11:00")
def test_next_batch_slot_on_same_day():
    scheduler = Scheduler(time(22, 0), time(6, 0))
    next_slot = datetime(2020, 11, 5, 22, 0)
    next_slot = timezone.make_aware(next_slot)
    assert scheduler.next_slot() == next_slot


@time_machine.travel("2020-11-05 23:00")
def test_next_batch_slot_on_next_day():
    scheduler = Scheduler(time(22, 0), time(6, 0))
    next_slot = datetime(2020, 11, 6, 22, 0)
    next_slot = timezone.make_aware(next_slot)
    assert scheduler.next_slot() == next_slot
