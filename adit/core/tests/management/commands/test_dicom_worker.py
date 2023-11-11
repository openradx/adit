import argparse
from datetime import time

import pytest

from adit.core.management.commands.dicom_worker import in_time_slot, valid_time_range


def test_in_time_slot():
    assert in_time_slot(time(10), time(20), time(15))
    assert in_time_slot(time(20), time(6), time(3))
    assert not in_time_slot(time(20), time(6), time(15))


def test_valid_time_range():
    assert valid_time_range("10:00-20:00") == (time(10), time(20))
    assert valid_time_range("10:00-06:00") == (time(10), time(6))

    with pytest.raises(argparse.ArgumentTypeError):
        assert not valid_time_range("10-6:00")
