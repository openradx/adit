from datetime import time
from django.test import TestCase
from batch_transfer.utils.task_utils import is_time_between


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
