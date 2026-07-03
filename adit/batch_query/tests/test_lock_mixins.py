"""Regression test for the batch_query task views' lock mixin (upstream #337).

The task views (Delete/Reset/Kill) must be gated by the *batch_query* section's
lock setting via ``BatchQueryLockedMixin`` — not by another app's lock mixin
(they previously used ``SelectiveTransferLockedMixin``, a wiring bug).
"""

from adit.batch_query.mixins import BatchQueryLockedMixin
from adit.batch_query.views import (
    BatchQueryTaskDeleteView,
    BatchQueryTaskKillView,
    BatchQueryTaskResetView,
)
from adit.selective_transfer.mixins import SelectiveTransferLockedMixin

TASK_VIEWS = (
    BatchQueryTaskDeleteView,
    BatchQueryTaskResetView,
    BatchQueryTaskKillView,
)


def test_batch_query_task_views_use_batch_query_lock_mixin():
    for view in TASK_VIEWS:
        assert issubclass(view, BatchQueryLockedMixin)


def test_batch_query_task_views_not_gated_by_selective_transfer_lock():
    for view in TASK_VIEWS:
        assert not issubclass(view, SelectiveTransferLockedMixin)
