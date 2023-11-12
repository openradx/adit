from datetime import time

from ...utils.worker_utils import in_time_slot


def test_in_time_slot():
    assert in_time_slot(time(10), time(20), time(15))
    assert in_time_slot(time(20), time(6), time(3))
    assert not in_time_slot(time(20), time(6), time(15))
