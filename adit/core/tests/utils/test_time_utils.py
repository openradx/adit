import argparse
from datetime import time

import pytest

from ...utils.time_utils import valid_time_range


def test_valid_time_range():
    assert valid_time_range("10:00-20:00") == (time(10), time(20))
    assert valid_time_range("10:00-06:00") == (time(10), time(6))

    with pytest.raises(argparse.ArgumentTypeError):
        assert not valid_time_range("10-6:00")
