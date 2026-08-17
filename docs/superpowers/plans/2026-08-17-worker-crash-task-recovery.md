# Worker-Crash Task Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair `DicomTask` rows left `IN_PROGRESS` by a killed worker (periodic + boot-time sweep) and make the task claim in `_run_dicom_task` a strict `PENDING → IN_PROGRESS` compare-and-set.

**Architecture:** A new module `adit/core/utils/recovery.py` selects `IN_PROGRESS` tasks whose Procrastinate queue row is gone / finished / owned by a dead worker, resets each with a conditional UPDATE (to `PENDING`, or `CANCELED` under a canceling job), re-queues it via the model's own `queue_pending_task()` only when the old row will not fire again, and re-evaluates affected jobs with `post_process()`. It runs from a management command (before `bg_worker` in every worker container) and from a periodic Procrastinate task. `_run_dicom_task` claims tasks with one conditional UPDATE and skips deliveries it cannot claim.

**Tech Stack:** Django 5 ORM, Procrastinate 3.x (Django contrib models `ProcrastinateJob`, `ProcrastinateWorker`), pglock, pytest-django, factory-boy.

**Spec:** `docs/superpowers/specs/2026-08-17-worker-crash-task-recovery-design.md`

## Global Constraints

- Python 3.12+, Django 5.1, `procrastinate[django]>=3.0.2` (3.9.0 installed) — do not add dependencies.
- Line length 100 (Ruff), Google style, pyright basic. Run `uv run cli lint` before every commit.
- Comments: plain "what + one short why", 2–3 lines, everyday words. Say "run again after a crash", not "re-fire"; "queue row" for `procrastinate_jobs`, "job/task" for `DicomJob`/`DicomTask`. No history in comments.
- `assert` only for internal invariants; entry-point status checks are guards that warn and return.
- Settings names: `DICOM_TASK_STALLED_WORKER_GRACE_SECONDS` (default 30), `DICOM_TASK_SWEEP_CRON` (default `* * * * *`).
- Stale-task message text, verbatim: `The worker processing this task was terminated.`
- Tests: `uv run cli test -- <path>`; they run inside the `web` container. If the container image is stale, `uv run cli compose-up -- -d --build` first (see notes §8 in `docs/superpowers/notes/2026-08-17-worker-crash-recovery-handoff-from-radis.md`).
- Commit messages: imperative subject; end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Branch: `worker-crash-task-recovery` (already created, spec committed on it).

## File structure

| File | Responsibility |
|---|---|
| `adit/core/utils/model_utils.py` (modify) | Gains `DICOM_JOB_POST_PROCESS_LOCK` (moved from `tasks.py`) so both `tasks.py` and `recovery.py` can use it without a circular import |
| `adit/core/utils/recovery.py` (create) | Owner-gone predicate, `_resolve_stale_task`, `sweep_stale_dicom_tasks` |
| `adit/core/tests/utils/test_recovery.py` (create) | Sweep unit + end-to-end (DB-only) tests |
| `adit/core/tasks.py` (modify) | Strict CAS claim; periodic sweep task |
| `adit/core/tests/test_tasks.py` (modify) | Claim tests |
| `adit/core/management/commands/sweep_stale_tasks.py` (create) | Boot-time command, never exits non-zero |
| `adit/core/tests/test_management.py` (create) | Command test |
| `adit/settings/base.py`, `example.env` (modify) | Two settings |
| `docker-compose.dev.yml`, `docker-compose.prod.yml` (modify) | `sweep_stale_tasks &&` before `bg_worker` in the three worker services |
| `AGENTS.md`, `KNOWLEDGE.md` (modify) | Docs |

---

### Task 1: Settings, lock constant, and the owner-gone predicate

**Files:**
- Modify: `adit/settings/base.py:420-422` (next to `STALLED_JOBS_RETRY_PRIORITY`)
- Modify: `example.env` (after `MASS_TRANSFER_WORKER_REPLICAS`)
- Modify: `adit/core/utils/model_utils.py`
- Modify: `adit/core/tasks.py:23,167`
- Create: `adit/core/utils/recovery.py`
- Test: `adit/core/tests/utils/test_recovery.py`

**Interfaces:**
- Produces: `settings.DICOM_TASK_STALLED_WORKER_GRACE_SECONDS: int`, `settings.DICOM_TASK_SWEEP_CRON: str`; `adit.core.utils.model_utils.DICOM_JOB_POST_PROCESS_LOCK: str`; `recovery._owner_gone_q(cutoff: datetime) -> Q`; `recovery.dicom_task_models() -> list[type[DicomTask]]`; `recovery.STALE_TASK_MESSAGE: str`.

- [ ] **Step 1: Add the settings**

In `adit/settings/base.py`, directly after `STALLED_JOBS_RETRY_PRIORITY = 10`:

```python
# A task still IN_PROGRESS whose queue row is gone, or whose worker sent no heartbeat
# for this many seconds, is treated as abandoned and repaired by the sweep.
# Never below 30: Procrastinate itself declares a worker stalled after 30 s, and a
# stricter value here would reset tasks whose worker is merely slow, running them twice.
DICOM_TASK_STALLED_WORKER_GRACE_SECONDS = env.int(
    "DICOM_TASK_STALLED_WORKER_GRACE_SECONDS", default=30
)

# Cron schedule of the periodic sweep that repairs tasks left IN_PROGRESS by killed workers.
DICOM_TASK_SWEEP_CRON = env.str("DICOM_TASK_SWEEP_CRON", default="* * * * *")
```

In `example.env`, after the `MASS_TRANSFER_WORKER_REPLICAS=5` line:

```
# Tasks whose worker stopped sending heartbeats for this many seconds are treated
# as abandoned and put back to pending. Never set below 30.
DICOM_TASK_STALLED_WORKER_GRACE_SECONDS=30

# How often the sweep for abandoned tasks runs (cron syntax, default every minute).
DICOM_TASK_SWEEP_CRON=* * * * *
```

- [ ] **Step 2: Move the advisory-lock name into `model_utils.py`**

In `adit/core/utils/model_utils.py`, after the imports:

```python
# One advisory lock for every job re-evaluation (task finalizer and sweep alike), so two
# writers never interleave their reads of the task statuses and their job save.
DICOM_JOB_POST_PROCESS_LOCK = "process_dicom_task_lock"
```

In `adit/core/tasks.py`: delete the line `DISTRIBUTED_LOCK = "process_dicom_task_lock"`, add `from .utils.model_utils import DICOM_JOB_POST_PROCESS_LOCK` next to the other `.utils` imports, and change `with pglock.advisory(DISTRIBUTED_LOCK):` to `with pglock.advisory(DICOM_JOB_POST_PROCESS_LOCK):`.

Run: `uv run cli test -- adit/core/tests/test_tasks.py -q` → all pass (pure rename).

- [ ] **Step 3: Write the failing predicate tests**

Create `adit/core/tests/utils/test_recovery.py`:

```python
from datetime import timedelta

import pytest
from django.utils import timezone
from procrastinate.contrib.django.models import ProcrastinateJob, ProcrastinateWorker

from adit.core.models import DicomJob, DicomTask
from adit.core.utils import recovery

from ..example_app.factories import ExampleTransferJobFactory, ExampleTransferTaskFactory
from ..example_app.models import ExampleTransferTask


@pytest.fixture(autouse=True)
def writable_procrastinate(settings):
    # Procrastinate's Django models are read-only by default; the tests create rows.
    settings.PROCRASTINATE_READONLY_MODELS = False


def create_worker(heartbeat_age_seconds: int) -> ProcrastinateWorker:
    return ProcrastinateWorker.objects.create(
        last_heartbeat=timezone.now() - timedelta(seconds=heartbeat_age_seconds)
    )


def create_row(status: str, worker: ProcrastinateWorker | None = None) -> ProcrastinateJob:
    return ProcrastinateJob.objects.create(
        queue_name="dicom",
        task_name="adit.core.tasks.process_dicom_task",
        priority=0,
        args={},
        status=status,
        attempts=0,
        abort_requested=False,
        worker=worker,
    )


def make_stale_task(job_status: str, row: ProcrastinateJob | None) -> ExampleTransferTask:
    job = ExampleTransferJobFactory.create(status=job_status)
    return ExampleTransferTaskFactory.create(
        job=job, status=DicomTask.Status.IN_PROGRESS, queued_job=row
    )


def owner_gone_q():
    return recovery._owner_gone_q(timezone.now() - timedelta(seconds=30))


def stale_candidates():
    return ExampleTransferTask.objects.filter(status=DicomTask.Status.IN_PROGRESS).filter(
        owner_gone_q()
    )


@pytest.mark.django_db
def test_task_models_include_every_concrete_dicom_task():
    models = recovery.dicom_task_models()
    assert ExampleTransferTask in models
    assert all(issubclass(m, DicomTask) and not m._meta.abstract for m in models)


@pytest.mark.django_db
def test_predicate_matches_task_without_row():
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)
    assert list(stale_candidates()) == [task]


@pytest.mark.django_db
@pytest.mark.parametrize("row_status", ["todo", "succeeded", "failed", "cancelled", "aborted"])
def test_predicate_matches_row_nobody_is_running(row_status):
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=create_row(row_status))
    assert list(stale_candidates()) == [task]


@pytest.mark.django_db
def test_predicate_matches_doing_row_without_worker():
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=create_row("doing", worker=None))
    assert list(stale_candidates()) == [task]


@pytest.mark.django_db
def test_predicate_matches_doing_row_with_stale_heartbeat():
    row = create_row("doing", worker=create_worker(heartbeat_age_seconds=60))
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)
    assert list(stale_candidates()) == [task]


@pytest.mark.django_db
def test_predicate_ignores_doing_row_with_fresh_heartbeat():
    # A task may legitimately run for hours in its subprocess; the parent worker keeps
    # sending heartbeats, so it is not stale.
    row = create_row("doing", worker=create_worker(heartbeat_age_seconds=0))
    make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)
    assert not stale_candidates().exists()


@pytest.mark.django_db
def test_predicate_ignores_aborting_row_with_fresh_heartbeat():
    row = create_row("aborting", worker=create_worker(heartbeat_age_seconds=0))
    make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)
    assert not stale_candidates().exists()
```

- [ ] **Step 4: Run to verify they fail**

Run: `uv run cli test -- adit/core/tests/utils/test_recovery.py -q`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'adit.core.utils.recovery'`.

- [ ] **Step 5: Create `recovery.py` with the predicate**

```python
import logging
from datetime import datetime

from django.apps import apps
from django.db.models import Q
from procrastinate.jobs import Status

from ..models import DicomJob, DicomTask

logger = logging.getLogger(__name__)

STALE_TASK_MESSAGE = "The worker processing this task was terminated."

# A worker owns the row and is running it right now.
_RUNNING_ROW_STATUSES = [Status.DOING.value, Status.ABORTING.value]

# Nobody is running the row: it waits to be picked up (todo) or it is finished.
_INACTIVE_ROW_STATUSES = [s.value for s in Status if s.value not in _RUNNING_ROW_STATUSES]

# The row will still fire (or is running): do not create a second one for the same task.
_LIVE_ROW_STATUSES = [Status.TODO.value, *_RUNNING_ROW_STATUSES]

_TERMINAL_JOB_STATUSES = (
    DicomJob.Status.CANCELED,
    DicomJob.Status.SUCCESS,
    DicomJob.Status.WARNING,
    DicomJob.Status.FAILURE,
)


def dicom_task_models() -> list[type[DicomTask]]:
    return [m for m in apps.get_models() if issubclass(m, DicomTask)]


def _owner_gone_q(cutoff: datetime) -> Q:
    """Match tasks whose worker is gone: queue row missing, finished, or worker silent.

    Written as OR-ed positive conditions. An .exclude() over the nullable queued_job
    join would silently drop tasks that have no queue row at all.
    """
    return (
        # queue row deleted (workers run with --delete-jobs=always)
        Q(queued_job__isnull=True)
        # queue row exists but nobody is running it: waiting to be picked up, or finished
        | Q(queued_job__status__in=_INACTIVE_ROW_STATUSES)
        # a worker claimed the row, but its worker record is gone
        | Q(queued_job__status__in=_RUNNING_ROW_STATUSES, queued_job__worker__isnull=True)
        # a worker claimed the row, but stopped sending heartbeats
        | Q(
            queued_job__status__in=_RUNNING_ROW_STATUSES,
            queued_job__worker__last_heartbeat__lt=cutoff,
        )
    )
```

- [ ] **Step 6: Run to verify they pass**

Run: `uv run cli test -- adit/core/tests/utils/test_recovery.py -q`
Expected: 10 passed.

- [ ] **Step 7: Lint and commit**

```bash
uv run cli lint
git add adit/settings/base.py example.env adit/core/utils/model_utils.py adit/core/tasks.py adit/core/utils/recovery.py adit/core/tests/utils/test_recovery.py
git commit -m "Add owner-gone predicate and settings for stale task recovery

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Resolve one stale task (conditional reset + re-queue in one transaction)

**Files:**
- Modify: `adit/core/utils/recovery.py`
- Test: `adit/core/tests/utils/test_recovery.py`

**Interfaces:**
- Consumes: `_owner_gone_q`, `STALE_TASK_MESSAGE`, `_LIVE_ROW_STATUSES` from Task 1; `DicomTask.queue_pending_task()` (`adit/core/models.py:429`, overridden by `MassTransferTask`).
- Produces: `recovery._resolve_stale_task(task: DicomTask, owner_gone: Q) -> str | None` returning `"pending"`, `"canceled"`, or `None` (nothing done).

- [ ] **Step 1: Write the failing resolve tests**

Append to `adit/core/tests/utils/test_recovery.py`:

```python
from unittest.mock import patch  # add to the imports at the top

from django.db import connection  # add to the imports at the top

from adit.mass_transfer.factories import (  # add to the imports at the top
    MassTransferJobFactory,
    MassTransferTaskFactory,
)
from adit.mass_transfer.models import MassTransferTask  # add to the imports at the top


@pytest.mark.django_db
def test_resolve_orphan_under_live_job_resets_and_requeues():
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)
    task.attempts = 2
    task.save()

    assert recovery._resolve_stale_task(task, owner_gone_q()) == "pending"

    task.refresh_from_db()
    assert task.status == DicomTask.Status.PENDING
    assert task.message == recovery.STALE_TASK_MESSAGE
    assert task.end is None
    assert task.attempts == 2  # the sweep never touches the attempt counter
    assert task.queued_job is not None
    assert task.queued_job.status == "todo"
    assert task.queued_job.task_name == "adit.core.tasks.process_dicom_task"
    assert task.queued_job.queue_name == "dicom"


@pytest.mark.django_db
def test_resolve_mass_transfer_task_requeues_on_its_own_queue():
    job = MassTransferJobFactory.create(status=DicomJob.Status.IN_PROGRESS)
    task = MassTransferTaskFactory.create(
        job=job, status=DicomTask.Status.IN_PROGRESS, queued_job=None
    )

    assert recovery._resolve_stale_task(task, owner_gone_q()) == "pending"

    task.refresh_from_db()
    assert task.queued_job is not None
    assert task.queued_job.task_name == "adit.mass_transfer.tasks.process_mass_transfer_task"
    assert task.queued_job.queue_name == "mass_transfer"


@pytest.mark.django_db
@pytest.mark.parametrize("job_status", [DicomJob.Status.CANCELING, DicomJob.Status.CANCELED])
def test_resolve_under_canceling_job_cancels_without_requeue(job_status):
    task = make_stale_task(job_status, row=None)

    assert recovery._resolve_stale_task(task, owner_gone_q()) == "canceled"

    task.refresh_from_db()
    assert task.status == DicomTask.Status.CANCELED
    assert task.message == recovery.STALE_TASK_MESSAGE
    assert task.end is not None
    assert task.queued_job is None
    assert not ProcrastinateJob.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("row_status", ["todo", "doing"])
def test_resolve_keeps_live_row_and_does_not_requeue(row_status):
    # retry_stalled_jobs will re-deliver this very row; a second row would run the task twice.
    row = create_row(row_status, worker=create_worker(heartbeat_age_seconds=60))
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)

    assert recovery._resolve_stale_task(task, owner_gone_q()) == "pending"

    task.refresh_from_db()
    assert task.status == DicomTask.Status.PENDING
    assert task.queued_job is None  # link cleared; the row itself is untouched
    assert ProcrastinateJob.objects.count() == 1
    assert ProcrastinateJob.objects.get(pk=row.pk).status == row_status


@pytest.mark.django_db
def test_resolve_declines_when_a_live_worker_owns_the_row():
    row = create_row("doing", worker=create_worker(heartbeat_age_seconds=0))
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)

    assert recovery._resolve_stale_task(task, owner_gone_q()) is None

    task.refresh_from_db()
    assert task.status == DicomTask.Status.IN_PROGRESS
    assert task.queued_job_id == row.pk


@pytest.mark.django_db
def test_resolve_declines_when_task_already_finished():
    # The candidate was selected while IN_PROGRESS; the worker finished it in the meantime.
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)
    ExampleTransferTask.objects.filter(pk=task.pk).update(status=DicomTask.Status.SUCCESS)

    assert recovery._resolve_stale_task(task, owner_gone_q()) is None

    task.refresh_from_db()
    assert task.status == DicomTask.Status.SUCCESS
    assert not ProcrastinateJob.objects.exists()


@pytest.mark.django_db
def test_resolve_twice_changes_nothing_the_second_time():
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)
    stale_copy = ExampleTransferTask.objects.get(pk=task.pk)  # a second sweep's candidate

    assert recovery._resolve_stale_task(task, owner_gone_q()) == "pending"
    assert recovery._resolve_stale_task(stale_copy, owner_gone_q()) is None

    assert ProcrastinateJob.objects.count() == 1


@pytest.mark.django_db
def test_requeue_decision_uses_fresh_read_not_snapshot():
    # The row is deleted between selecting the task and resolving it. The resolve step must
    # notice and re-queue, else the task stays PENDING with no row forever.
    row = create_row("todo", worker=create_worker(heartbeat_age_seconds=60))
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)
    task = ExampleTransferTask.objects.select_related("queued_job").get(pk=task.pk)

    with connection.cursor() as cursor:  # raw delete, like Procrastinate's --delete-jobs
        cursor.execute("DELETE FROM procrastinate_jobs WHERE id = %s", [row.pk])

    assert recovery._resolve_stale_task(task, owner_gone_q()) == "pending"

    task.refresh_from_db()
    assert task.queued_job is not None
    assert task.queued_job.pk != row.pk


@pytest.mark.django_db(transaction=True)
def test_reset_rolls_back_when_requeue_fails():
    # If queuing fails after the reset, the task must stay IN_PROGRESS so the next sweep
    # retries it. A PENDING task without a queue row would never run again.
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)

    with patch.object(
        ExampleTransferTask, "queue_pending_task", autospec=True, side_effect=RuntimeError("db")
    ):
        with pytest.raises(RuntimeError):
            recovery._resolve_stale_task(task, owner_gone_q())

    task.refresh_from_db()
    assert task.status == DicomTask.Status.IN_PROGRESS
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run cli test -- adit/core/tests/utils/test_recovery.py -q`
Expected: the new tests FAIL with `AttributeError: module ... has no attribute '_resolve_stale_task'`; Task 1 tests still pass.

- [ ] **Step 3: Implement `_resolve_stale_task`**

Add to `adit/core/utils/recovery.py` (extend imports: `from django.db import transaction`, `from django.utils import timezone`, `from procrastinate.contrib.django.models import ProcrastinateJob`):

```python
def _resolve_stale_task(task: DicomTask, owner_gone: Q) -> str | None:
    """Reset one stale task. Returns "pending"/"canceled", or None if it was no longer stale."""
    model = type(task)
    job = task.job

    if job.status in (DicomJob.Status.CANCELING, DicomJob.Status.CANCELED):
        new_status = DicomTask.Status.CANCELED
        end = timezone.now()
    else:
        new_status = DicomTask.Status.PENDING
        end = None

    old_row_id = task.queued_job_id  # the UPDATE below clears the link

    # Reset and re-queue in one transaction: if queuing fails, the reset rolls back and
    # the next sweep tries again. A PENDING task without a queue row would never run.
    with transaction.atomic():
        # The WHERE re-checks status and owner inside the UPDATE itself, so nothing
        # happens if a live worker or another sweep got to this task first.
        updated = (
            model.objects.filter(pk=task.pk, status=DicomTask.Status.IN_PROGRESS)
            .filter(owner_gone)
            .update(status=new_status, message=STALE_TASK_MESSAGE, end=end, queued_job_id=None)
        )
        if not updated:
            return None

        if new_status == DicomTask.Status.PENDING:
            # Re-queue only if the old row will not run again. Read the DB fresh, not our
            # candidate snapshot: the row may have been deleted since we selected the task.
            row_alive = (
                old_row_id is not None
                and ProcrastinateJob.objects.filter(
                    pk=old_row_id, status__in=_LIVE_ROW_STATUSES
                ).exists()
            )
            if not row_alive:
                task.refresh_from_db()  # queue_pending_task() saves the whole task
                task.queue_pending_task()

    return "pending" if new_status == DicomTask.Status.PENDING else "canceled"
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run cli test -- adit/core/tests/utils/test_recovery.py -q`
Expected: all pass. If `test_resolve_mass_transfer_task_requeues_on_its_own_queue` errors on factory fields, check `adit/mass_transfer/factories.py` for required fields (`partition_start`, `partition_end`, `partition_key`) and pass them explicitly.

- [ ] **Step 5: Lint and commit**

```bash
uv run cli lint
git add adit/core/utils/recovery.py adit/core/tests/utils/test_recovery.py
git commit -m "Reset and re-queue a stale dicom task in one transaction

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: The sweep across all task models, job re-evaluation, logging

**Files:**
- Modify: `adit/core/utils/recovery.py`
- Test: `adit/core/tests/utils/test_recovery.py`

**Interfaces:**
- Consumes: `dicom_task_models`, `_owner_gone_q`, `_resolve_stale_task` (Tasks 1–2); `DicomJob.post_process()` (`adit/core/models.py:258`); `DICOM_JOB_POST_PROCESS_LOCK`.
- Produces: `recovery.sweep_stale_dicom_tasks() -> None`.

- [ ] **Step 1: Write the failing sweep tests**

Append to `adit/core/tests/utils/test_recovery.py` (add `import logging` at the top):

```python
@pytest.mark.django_db
def test_sweep_drains_job_stuck_in_canceling():
    # Worker killed while a task ran, row gone, user pressed Cancel: nothing ends the job.
    task = make_stale_task(DicomJob.Status.CANCELING, row=None)

    recovery.sweep_stale_dicom_tasks()

    task.refresh_from_db()
    task.job.refresh_from_db()
    assert task.status == DicomTask.Status.CANCELED
    assert task.job.status == DicomJob.Status.CANCELED
    assert not ProcrastinateJob.objects.exists()


@pytest.mark.django_db
def test_sweep_requeues_orphan_and_job_goes_back_to_pending():
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)

    recovery.sweep_stale_dicom_tasks()

    task.refresh_from_db()
    task.job.refresh_from_db()
    assert task.status == DicomTask.Status.PENDING
    assert task.queued_job is not None
    assert task.job.status == DicomJob.Status.PENDING


@pytest.mark.django_db
def test_sweep_leaves_running_and_finished_tasks_alone():
    running = make_stale_task(
        DicomJob.Status.IN_PROGRESS,
        row=create_row("doing", worker=create_worker(heartbeat_age_seconds=0)),
    )
    job = ExampleTransferJobFactory.create(status=DicomJob.Status.IN_PROGRESS)
    pending = ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.PENDING)
    done = ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)

    recovery.sweep_stale_dicom_tasks()

    for task, status in (
        (running, DicomTask.Status.IN_PROGRESS),
        (pending, DicomTask.Status.PENDING),
        (done, DicomTask.Status.SUCCESS),
    ):
        task.refresh_from_db()
        assert task.status == status
    assert ProcrastinateJob.objects.count() == 1


@pytest.mark.django_db
def test_sweep_reevaluates_finished_job_with_stray_in_progress_task():
    # Should not happen, but a repaired task must never hang under a finished job.
    job = ExampleTransferJobFactory.create(status=DicomJob.Status.SUCCESS)
    ExampleTransferTaskFactory.create(job=job, status=DicomTask.Status.SUCCESS)
    stray = ExampleTransferTaskFactory.create(
        job=job, status=DicomTask.Status.IN_PROGRESS, queued_job=None
    )

    recovery.sweep_stale_dicom_tasks()

    stray.refresh_from_db()
    job.refresh_from_db()
    assert stray.status == DicomTask.Status.PENDING
    assert job.status == DicomJob.Status.PENDING


@pytest.mark.django_db
def test_sweep_covers_every_task_model():
    example = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)
    mass_job = MassTransferJobFactory.create(status=DicomJob.Status.IN_PROGRESS)
    mass = MassTransferTaskFactory.create(
        job=mass_job, status=DicomTask.Status.IN_PROGRESS, queued_job=None
    )

    recovery.sweep_stale_dicom_tasks()

    example.refresh_from_db()
    mass.refresh_from_db()
    assert example.status == DicomTask.Status.PENDING
    assert mass.status == DicomTask.Status.PENDING


@pytest.mark.django_db
def test_sweep_logs_info_only_when_something_was_repaired(caplog):
    caplog.set_level(logging.DEBUG, logger="adit.core.utils.recovery")

    recovery.sweep_stale_dicom_tasks()
    assert not [r for r in caplog.records if r.levelno == logging.INFO]

    make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)
    recovery.sweep_stale_dicom_tasks()
    info = [r for r in caplog.records if r.levelno == logging.INFO]
    assert len(info) == 1
    assert "ExampleTransferTask 1 (1 pending, 0 canceled)" in info[0].getMessage()
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run cli test -- adit/core/tests/utils/test_recovery.py -q -k sweep`
Expected: FAIL with `AttributeError: ... 'sweep_stale_dicom_tasks'`.

- [ ] **Step 3: Implement `sweep_stale_dicom_tasks`**

Add to `adit/core/utils/recovery.py` (extend imports: `from datetime import datetime, timedelta`, `import pglock`, `from django.conf import settings`, `from .model_utils import DICOM_JOB_POST_PROCESS_LOCK`):

```python
def sweep_stale_dicom_tasks() -> None:
    """Repair tasks left IN_PROGRESS by a killed worker, across all DicomTask models."""
    cutoff = timezone.now() - timedelta(seconds=settings.DICOM_TASK_STALLED_WORKER_GRACE_SECONDS)
    owner_gone = _owner_gone_q(cutoff)

    summary: list[str] = []
    repaired_total = 0
    affected_jobs: dict[tuple[str, int], DicomJob] = {}

    for model in dicom_task_models():
        pending = canceled = 0
        candidates = (
            model.objects.filter(status=DicomTask.Status.IN_PROGRESS)
            .filter(owner_gone)
            .select_related("job", "queued_job", "queued_job__worker")
        )
        for task in candidates:
            outcome = _resolve_stale_task(task, owner_gone)
            if outcome == "pending":
                pending += 1
            elif outcome == "canceled":
                canceled += 1
            else:
                continue
            affected_jobs[(task.job._meta.label, task.job.pk)] = task.job

        repaired_total += pending + canceled
        summary.append(f"{model.__name__} {pending + canceled} ({pending} pending, {canceled} canceled)")

    for job in affected_jobs.values():
        # Recompute the job from its tasks, under the same lock the task finalizer uses.
        # A finished job is recomputed too if it still has open tasks: a repaired task
        # must never hang under a job that already reports a final result.
        with pglock.advisory(DICOM_JOB_POST_PROCESS_LOCK):
            job.refresh_from_db()
            has_open_tasks = job.tasks.filter(
                status__in=(DicomTask.Status.PENDING, DicomTask.Status.IN_PROGRESS)
            ).exists()
            if job.status not in _TERMINAL_JOB_STATUSES or has_open_tasks:
                job.post_process()

    message = "Stale dicom task sweep: " + ", ".join(summary)
    if repaired_total:
        logger.info(message)
    else:
        logger.debug(message)
```

Note: `post_process()` on a job whose tasks are all `SUCCESS` sends the finished mail if `send_finished_mail` is set. Only jobs with an actually repaired task get here, so a job goes back to `PENDING`/`CANCELED`, never straight to `SUCCESS`; no duplicate mail.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run cli test -- adit/core/tests/utils/test_recovery.py -q`
Expected: all pass. The summary line for the mass-transfer test also lists other models with `0`; the assertion only checks the substring.

- [ ] **Step 5: Lint and commit**

```bash
uv run cli lint
git add adit/core/utils/recovery.py adit/core/tests/utils/test_recovery.py
git commit -m "Sweep stale dicom tasks across all task models and re-evaluate their jobs

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Strict task claim in `_run_dicom_task`

**Files:**
- Modify: `adit/core/tasks.py:59-90`
- Test: `adit/core/tests/test_tasks.py:445-468` (replace `test_run_dicom_task_accepts_in_progress_task_on_retry`) and new tests

**Interfaces:**
- Consumes: nothing new.
- Produces: `_run_dicom_task` returns early (without processing) when the task is not `PENDING`.

- [ ] **Step 1: Replace the tolerant test and add claim tests**

In `adit/core/tests/test_tasks.py`, delete `test_run_dicom_task_accepts_in_progress_task_on_retry` (lines 445–468) and add in its place:

```python
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "task_status", [DicomTask.Status.IN_PROGRESS, DicomTask.Status.SUCCESS]
)
def test_run_dicom_task_skips_delivery_when_task_is_not_pending(
    mocker: MockerFixture, task_status, caplog
):
    # Procrastinate delivers at least once. A row that arrives for a task another run
    # already claimed or finished must do nothing (the sweep repairs real orphans).
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.IN_PROGRESS)
    dicom_task = ExampleTransferTaskFactory.create(
        status=task_status, job=dicom_job, attempts=1, message="untouched"
    )
    model_label = get_model_label(ExampleTransferTask)
    process = mocker.patch.object(ExampleProcessor, "process")
    _install_pebble_stubs(mocker, future=_FakeFuture(result=None))

    tasks_module._run_dicom_task(_make_context(), model_label, dicom_task.pk)

    process.assert_not_called()
    dicom_task.refresh_from_db()
    dicom_job.refresh_from_db()
    assert dicom_task.status == task_status
    assert dicom_task.attempts == 1
    assert dicom_task.message == "untouched"
    assert dicom_job.status == DicomJob.Status.IN_PROGRESS
    assert any("skipping" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)


@pytest.mark.django_db(transaction=True)
def test_run_dicom_task_claim_increments_attempts_and_sets_start(mocker: MockerFixture):
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.PENDING)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING, job=dicom_job, attempts=2
    )
    model_label = get_model_label(ExampleTransferTask)
    result: ProcessingResult = {"status": DicomTask.Status.SUCCESS, "message": "", "log": ""}
    _install_pebble_stubs(mocker, future=_FakeFuture(result=result))

    tasks_module._run_dicom_task(_make_context(), model_label, dicom_task.pk)

    dicom_task.refresh_from_db()
    assert dicom_task.attempts == 3
    assert dicom_task.start is not None
    assert dicom_task.status == DicomTask.Status.SUCCESS
```

Add `import logging` to the test module imports.

- [ ] **Step 2: Run to verify the new tests fail**

Run: `uv run cli test -- adit/core/tests/test_tasks.py -q -k "skips_delivery or claim_increments"`
Expected: `skips_delivery[IN_PROGRESS]` FAILS (task is processed, `process` called); `skips_delivery[SUCCESS]` FAILS with `AssertionError` from the current status assert; `claim_increments` passes already (behaviour unchanged) — that is fine, it guards the rewrite.

- [ ] **Step 3: Rewrite the claim**

In `adit/core/tasks.py`, add `from django.db.models import F` to the imports, and replace lines from `dicom_task = get_dicom_task(model_label, task_id)` through `logger.info(f"Processing of {dicom_task} started.")` with:

```python
    dicom_task = get_dicom_task(model_label, task_id)

    # Claim the task with one UPDATE. Procrastinate delivers at least once, so a row can
    # arrive after another run already claimed or finished this task; then we do nothing
    # and let the row finish. A task left IN_PROGRESS by a killed worker is put back to
    # PENDING by the stale task sweep (adit/core/utils/recovery.py).
    claimed = (
        type(dicom_task)
        .objects.filter(pk=task_id, status=DicomTask.Status.PENDING)
        .update(
            status=DicomTask.Status.IN_PROGRESS,
            start=timezone.now(),
            attempts=F("attempts") + 1,
        )
    )
    if not claimed:
        logger.warning(
            "%s is %s, not pending; skipping this delivery.",
            dicom_task,
            dicom_task.get_status_display(),
        )
        return
    dicom_task.refresh_from_db()

    # When the first DICOM task of a job is processed then the status of the
    # job switches from PENDING to IN_PROGRESS
    dicom_job = dicom_task.job
    if dicom_job.status == DicomJob.Status.PENDING:
        dicom_job.status = DicomJob.Status.IN_PROGRESS
        dicom_job.start = timezone.now()
        dicom_job.save()
        logger.info(f"Processing of {dicom_job} started.")

    logger.info(f"Processing of {dicom_task} started.")
```

Delete the old block (`assert dicom_task.status in (...)` with its comment, and the `dicom_task.status = IN_PROGRESS / start / attempts += 1 / save()` lines).

- [ ] **Step 4: Run the whole task test module**

Run: `uv run cli test -- adit/core/tests/test_tasks.py -q`
Expected: all pass, including the retriable-error tests (retry semantics unchanged) and `test_process_dicom_task_transitions_to_failure_after_max_retries`.

- [ ] **Step 5: Lint and commit**

```bash
uv run cli lint
git add adit/core/tasks.py adit/core/tests/test_tasks.py
git commit -m "Claim dicom tasks with a conditional update instead of a status assert

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Management command, periodic task, compose wiring

**Files:**
- Create: `adit/core/management/commands/sweep_stale_tasks.py`
- Create: `adit/core/tests/test_management.py`
- Modify: `adit/core/tasks.py` (imports + periodic task after `check_disk_space`)
- Modify: `docker-compose.dev.yml:47-72`, `docker-compose.prod.yml:57-88`

**Interfaces:**
- Consumes: `sweep_stale_dicom_tasks` (Task 3), `settings.DICOM_TASK_SWEEP_CRON` (Task 1).
- Produces: `./manage.py sweep_stale_tasks`; Procrastinate task `adit.core.tasks.sweep_stale_tasks_periodic`.

- [ ] **Step 1: Write the failing command test**

Create `adit/core/tests/test_management.py`:

```python
from unittest.mock import patch

import pytest
from django.core.management import call_command

from adit.core.models import DicomJob, DicomTask

from .example_app.factories import ExampleTransferJobFactory, ExampleTransferTaskFactory


@pytest.mark.django_db
def test_sweep_command_repairs_stale_task():
    job = ExampleTransferJobFactory.create(status=DicomJob.Status.CANCELING)
    task = ExampleTransferTaskFactory.create(
        job=job, status=DicomTask.Status.IN_PROGRESS, queued_job=None
    )

    call_command("sweep_stale_tasks")

    task.refresh_from_db()
    assert task.status == DicomTask.Status.CANCELED


@pytest.mark.django_db
def test_sweep_command_exits_zero_when_sweep_raises(capsys):
    # The command runs before bg_worker via &&; a failing sweep must not stop the worker.
    with patch(
        "adit.core.management.commands.sweep_stale_tasks.sweep_stale_dicom_tasks",
        side_effect=RuntimeError("boom"),
    ):
        call_command("sweep_stale_tasks")  # must not raise

    assert "failed" in capsys.readouterr().out
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run cli test -- adit/core/tests/test_management.py -q`
Expected: FAIL with `CommandError: Unknown command: 'sweep_stale_tasks'`.

- [ ] **Step 3: Create the command**

`adit/core/management/commands/sweep_stale_tasks.py`:

```python
import logging

from django.core.management.base import BaseCommand

from adit.core.utils.recovery import sweep_stale_dicom_tasks

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Repair DICOM tasks left IN_PROGRESS by a killed worker."

    def handle(self, *args, **options):
        self.stdout.write("Sweeping stale dicom tasks... ", ending="")
        self.stdout.flush()

        # Runs before bg_worker in the container start command (chained with &&), so it
        # must never fail: the worker must start even if the sweep breaks.
        try:
            sweep_stale_dicom_tasks()
        except Exception:
            logger.exception("Sweeping stale dicom tasks failed.")
            self.stdout.write("failed (see logs)")
        else:
            self.stdout.write("done")
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run cli test -- adit/core/tests/test_management.py -q`
Expected: 2 passed.

- [ ] **Step 5: Add the periodic task**

In `adit/core/tasks.py`, add `from .utils.recovery import sweep_stale_dicom_tasks` to the imports and, right after `check_disk_space`:

```python
@app.periodic(cron=settings.DICOM_TASK_SWEEP_CRON)
@app.task(queueing_lock="sweep_stale_tasks")
def sweep_stale_tasks_periodic(timestamp: int) -> None:
    # A failing run just logs an error; queueing_lock keeps runs from piling up.
    sweep_stale_dicom_tasks()
```

Verify import: `uv run python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','adit.settings.development'); django.setup(); import adit.core.tasks"` (or simply run the test module from Task 4 again — it imports `adit.core.tasks`).

- [ ] **Step 6: Wire the compose files**

`docker-compose.dev.yml` — in `default_worker`, `dicom_worker`, `mass_transfer_worker`, insert `./manage.py sweep_stale_tasks &&` on its own line before the `./manage.py bg_worker ...` line, e.g.:

```yaml
      bash -c "
        wait-for-it -s postgres.local:5432 -t ${WAIT_POSTGRES_TIMEOUT:-180} &&
        ./manage.py sweep_stale_tasks &&
        ./manage.py bg_worker -l debug -q dicom --autoreload
      "
```

`docker-compose.prod.yml` — same three services:

```yaml
      bash -c "
        wait-for-it -s postgres.local:5432 -t ${WAIT_POSTGRES_TIMEOUT:-180} &&
        ./manage.py sweep_stale_tasks &&
        ./manage.py bg_worker -q dicom
      "
```

Leave `retry_stalled_jobs` in `web` untouched. (In dev, a worker may boot before `web` has migrated a fresh database; the command then logs the failure and exits 0, and the periodic sweep covers it later.)

Validate: `docker compose -f docker-compose.base.yml -f docker-compose.dev.yml config >/dev/null` and the same with `docker-compose.prod.yml` (check `cli.py` / `uv run cli compose-up --help` for how the files are combined if the direct call needs env vars; `uv run cli compose-up -- --dry-run` is an alternative).

- [ ] **Step 7: Lint and commit**

```bash
uv run cli lint
git add adit/core/management/commands/sweep_stale_tasks.py adit/core/tests/test_management.py adit/core/tasks.py docker-compose.dev.yml docker-compose.prod.yml
git commit -m "Run the stale task sweep at worker start and every minute

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Documentation

**Files:**
- Modify: `AGENTS.md` (`CLAUDE.md`/`GEMINI.md` are symlinks to it — do not touch them): sections "Job/Task Processing Model" (line ~66), "Task Actions" table Kill row (line ~108), "Docker Services" (line ~125), "Environment Variables" (line ~135)
- Modify: `KNOWLEDGE.md` (add a "Procrastinate" section under `## Django`, or next to `## Docker`)

- [ ] **Step 1: AGENTS.md — processing model**

Replace in "Job/Task Processing Model": `Background workers (Procrastinate) poll and process tasks from two queues: `default` and `dicom`` with `three queues: `default`, `dicom` and `mass_transfer``.

Add a subsection after "Job and Task Statuses":

```markdown
### Worker Crash Recovery

Two layers hold the state of a running task and heal independently:

- **Queue rows** (`procrastinate_jobs`, `todo → doing → succeeded/failed`, deleted on finish). Healed by Procrastinate plus `retry_stalled_jobs` (web boot + every 10 min): a `doing` row whose worker heartbeat is older than 30 s goes back to `todo`.
- **Task rows** (`DicomTask`, `PENDING → IN_PROGRESS → …`). Only app code inside a running task moves them.

When a worker dies mid-task the task stays `IN_PROGRESS`. The stale task sweep (`adit/core/utils/recovery.py`) repairs it: every `IN_PROGRESS` task whose queue row is gone, finished, or owned by a worker silent for `DICOM_TASK_STALLED_WORKER_GRACE_SECONDS` (default 30, never lower) is put back to `PENDING` (or `CANCELED` if the job is canceling) with one conditional UPDATE and re-queued if its old row will not run again; affected jobs are re-evaluated with `post_process()`. It runs at every worker start (`./manage.py sweep_stale_tasks`, never exits non-zero) and periodically (`DICOM_TASK_SWEEP_CRON`, default every minute, `default` queue).

`_run_dicom_task` claims a task with a single `PENDING → IN_PROGRESS` UPDATE and skips the delivery otherwise — Procrastinate delivers at least once, so a row may arrive for a task another run already handled.

Accepted: a worker frozen for more than the grace period but still alive can lead to the same task running twice (idempotent at the PACS, wasted work only); a task that repeatedly kills its worker is revived without a cap until canceled; `PENDING` tasks without a queue row are not repaired (use Restart/Reset).
```

- [ ] **Step 2: AGENTS.md — Kill row**

Replace the Kill row's last two cells with: `Queued Procrastinate job is asked to abort (the row itself is not deleted while running)` and `Job status is not immediately changed; the task's processor sets it when it stops. If the worker is already dead, the stale task sweep repairs the task`.

- [ ] **Step 3: AGENTS.md — env vars and Docker services**

Under "Environment Variables" add:

```markdown
- `DICOM_TASK_STALLED_WORKER_GRACE_SECONDS`: Seconds without worker heartbeat before an `IN_PROGRESS` task counts as abandoned (default 30, never lower)
- `DICOM_TASK_SWEEP_CRON`: Schedule of the stale task sweep (default `* * * * *`)
```

Under "Docker Services" add `- **mass_transfer_worker**: Mass transfer task processor (Procrastinate queue: `mass_transfer`)` if missing, and append to the worker bullets: "each worker runs `sweep_stale_tasks` before `bg_worker`".

- [ ] **Step 4: KNOWLEDGE.md**

Add under `## Django` (before `## DICOM`):

```markdown
### Procrastinate delivers at least once

A queue row can be delivered again after a worker crash (`retry_stalled_jobs`), so a task
entry point may see a task that is not `PENDING`. Never `assert` on the status there:
claim with a conditional UPDATE and skip otherwise. Tasks left `IN_PROGRESS` by a dead
worker are repaired by `sweep_stale_dicom_tasks` (`adit/core/utils/recovery.py`), which
runs at worker start and every minute. `cleanup_jobs_and_tasks` remains the manual
sledgehammer that marks everything in progress as failed.
```

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md KNOWLEDGE.md
git commit -m "Document worker crash recovery

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Full verification

**Files:** none new.

- [ ] **Step 1: Full test suite and lint**

Run: `uv run cli lint` and `uv run cli test` (full). Expected: all green. If the dev image is stale, `uv run cli compose-up -- -d --build` first and re-run.

- [ ] **Step 2: Manual crash check under Docker**

1. `uv run cli compose-up -- -d` and log in as admin; create a selective transfer from orthanc1 to orthanc2 with a few studies (or run `./manage.py populate_example_data` first).
2. While a task is `IN_PROGRESS`: `docker compose kill dicom_worker`.
3. Watch `docker compose logs -f default_worker` — within ~1–2 min the periodic sweep logs `Stale dicom task sweep: SelectiveTransferTask 1 (1 pending, 0 canceled)`; the task page shows `PENDING`, the job `PENDING`.
4. `docker compose up -d dicom_worker` — its start log shows `Sweeping stale dicom tasks... done`, then the task runs to `SUCCESS`.
5. Repeat with Cancel pressed while the worker is dead: job `CANCELING` → after the sweep `CANCELED`.

Write the observed outcome (2–3 lines) into the PR description.

- [ ] **Step 3: Finish**

Invoke `superpowers:finishing-a-development-branch`.
