# Worker Crash Recovery — 9a/9b Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two bugs found in the RADIS post-review addendum (§9 of
`docs/superpowers/notes/2026-08-17-worker-crash-recovery-handoff-from-radis.md`) that also
exist on the `worker-crash-task-recovery` branch: (9a) the sweep erases the task→queue-row
link and then treats the healthy recovered run as stale, causing duplicate concurrent
execution on every normal crash recovery; (9b) one exception anywhere in the sweep loop
aborts the whole run and can strand a job in `CANCELING` forever.

**Architecture:** Three code changes. (1) The sweep's PENDING reset keeps `queued_job_id`
pointing at the old queue row when that row is left alive to re-fire; the link is nulled
only when the sweep enqueues a fresh row (the CANCELED branch keeps nulling always, because
the Resume view flips CANCELED tasks straight back to PENDING and `queue_pending_tasks()`
asserts a cleared link). (2) The claim UPDATE in `_run_dicom_task` additionally stamps
`queued_job_id` with the delivering row's id, so a running task always names its true
owner — the sweep then sees a live worker and leaves it alone, and Kill can abort recovered
runs. (3) Every entry of the sweep loop (each task repair, each job recount) gets its own
try/except; errors are logged with the object and counted, and the sweep raises one summary
`RuntimeError` at the end so the periodic run / boot command still reports failure.

**Tech Stack:** Django 5.1, Procrastinate 3 (PostgreSQL-backed queue), pytest with
pytest-django and pytest-mock, factory-boy.

**Spec:** `docs/superpowers/specs/2026-08-17-worker-crash-task-recovery-design.md` (Task 4
amends it) plus §9a/§9b of
`docs/superpowers/notes/2026-08-17-worker-crash-recovery-handoff-from-radis.md`.

## Global Constraints

- **NEVER push or merge.** Commit on the current branch `worker-crash-task-recovery` only.
  This is an explicit user instruction.
- Tests run inside the dev containers: `uv run cli test -- <path>` from the repo root
  `/workspaces/adit-radis-workspace/projects/adit`. The dev stack is already up
  (project `adit_dev`, web on port 8001) with `docker compose watch` syncing source —
  no rebuild needed after edits.
- Lint with `uv run cli lint` before each commit.
- Comment style (user requirement): plain *what* + one short *why*, 2–3 lines, everyday
  words. Say "run again after a crash", not "re-fire"; distinguish "queue row"
  (procrastinate_jobs) from "task" (DicomTask). No history in comments — describe the code
  as it is.
- `assert` is fine for internal invariants (the app never runs with `python -O`).
- Line length 100 (Ruff).
- Do not touch `AGENTS.md` symlinks `CLAUDE.md`/`GEMINI.md` — edit `AGENTS.md` only.

## Background (read before any task)

Two layers hold a running task's state. The **queue row** (`procrastinate_jobs`) is healed
by Procrastinate plus `retry_stalled_jobs` (every 10 min): a `doing` row whose worker
heartbeat is stale goes back to `todo` and is re-delivered. The **task row** (`DicomTask`)
is healed only by the sweep in `adit/core/utils/recovery.py`: an `IN_PROGRESS` task whose
owner is gone is reset to `PENDING` with one conditional UPDATE, and re-queued only if its
old row will not run again.

The 9a bug: the reset UPDATE always sets `queued_job_id=None`, even when it deliberately
leaves the old row alive to re-fire. When that row later re-fires on a healthy worker, the
claim flips the task to `IN_PROGRESS` but nothing restores the link — so the next sweep
tick reads `queued_job__isnull=True` as "owner gone", resets the healthy run mid-flight,
finds no old row id, and enqueues a second row. Two workers then run the same task.

---

### Task 1: Sweep keeps the link to a live queue row (9a, sweep side)

**Files:**
- Modify: `adit/core/utils/recovery.py` (function `_resolve_stale_task`, lines 62–102)
- Test: `adit/core/tests/utils/test_recovery.py`

**Interfaces:**
- Consumes: existing helpers in the test file (`create_worker`, `create_row`,
  `make_stale_task`, `owner_gone_q`) and `recovery._resolve_stale_task(task, owner_gone)`.
- Produces: `_resolve_stale_task` with the same signature and return values
  (`"pending" | "canceled" | None`); new behavior: on the PENDING branch the reset UPDATE
  no longer touches `queued_job_id`; the link is nulled in a second UPDATE only when the
  old row is not alive, immediately before re-queueing. Task 3 restructures the sweep loop
  around this function but does not change it.

- [ ] **Step 1: Update the existing test that encodes the bug, and add the two-tick regression test**

In `adit/core/tests/utils/test_recovery.py`, replace the whole test
`test_resolve_keeps_live_row_and_does_not_requeue` (lines 158–171) with:

```python
@pytest.mark.django_db
@pytest.mark.parametrize("row_status", ["todo", "doing"])
def test_resolve_keeps_live_row_and_its_link_and_does_not_requeue(row_status):
    # retry_stalled_jobs will re-deliver this very row; a second row would run the task
    # twice. The task keeps pointing at the row, so after the row runs again the sweep
    # still sees who owns the task.
    row = create_row(row_status, worker=create_worker(heartbeat_age_seconds=60))
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)

    assert recovery._resolve_stale_task(task, owner_gone_q()) == "pending"

    task.refresh_from_db()
    assert task.status == DicomTask.Status.PENDING
    assert task.queued_job_id == row.pk
    assert ProcrastinateJob.objects.count() == 1
    assert ProcrastinateJob.objects.get(pk=row.pk).status == row_status
```

Then add this test right after it (this is the exact test shape §9a of the notes says the
single-tick tests cannot replace):

```python
@pytest.mark.django_db
def test_second_sweep_tick_leaves_the_recovered_run_alone():
    # The 9a bug shape: crash -> sweep resets the task but leaves the row to run again ->
    # the row runs again on a healthy worker -> the next sweep tick must not touch the
    # running task or create a second row.
    row = create_row("doing", worker=create_worker(heartbeat_age_seconds=60))
    task = make_stale_task(DicomJob.Status.IN_PROGRESS, row=row)

    recovery.sweep_stale_dicom_tasks()

    task.refresh_from_db()
    assert task.status == DicomTask.Status.PENDING
    assert task.queued_job_id == row.pk

    # retry_stalled_jobs hands the same row to a healthy worker, whose claim takes the
    # task (mirrors the claim UPDATE in adit/core/tasks.py including the owner stamp).
    ProcrastinateJob.objects.filter(pk=row.pk).update(
        worker=create_worker(heartbeat_age_seconds=0)
    )
    claimed = ExampleTransferTask.objects.filter(
        pk=task.pk, status=DicomTask.Status.PENDING
    ).update(status=DicomTask.Status.IN_PROGRESS, start=timezone.now(), queued_job_id=row.pk)
    assert claimed == 1

    recovery.sweep_stale_dicom_tasks()

    task.refresh_from_db()
    assert task.status == DicomTask.Status.IN_PROGRESS
    assert task.queued_job_id == row.pk
    assert ProcrastinateJob.objects.count() == 1
```

- [ ] **Step 2: Run both tests to verify they fail**

Run:
`uv run cli test -- adit/core/tests/utils/test_recovery.py -k "keeps_live_row or second_sweep_tick" -v`

Expected: 3 FAIL (two parametrized cases assert `queued_job_id == row.pk` but the current
code nulls it; the two-tick test fails at the same first assertion).

- [ ] **Step 3: Rewrite `_resolve_stale_task` to keep the link when the row stays alive**

In `adit/core/utils/recovery.py`, replace the whole function `_resolve_stale_task`
(lines 62–102) with:

```python
def _resolve_stale_task(task: DicomTask, owner_gone: Q) -> str | None:
    """Reset one stale task. Returns "pending"/"canceled", or None if it was no longer stale."""
    model = type(task)
    job = task.job

    old_row_id = task.queued_job_id

    # Reset and re-queue in one transaction: if queuing fails, the reset rolls back and
    # the next sweep tries again. A PENDING task without a queue row would never run.
    with transaction.atomic():
        if job.status in (DicomJob.Status.CANCELING, DicomJob.Status.CANCELED):
            # The link is always cleared here: Resume turns CANCELED tasks back into
            # PENDING ones and queues them fresh, which requires a cleared link. If the
            # old row still runs again, it finds the task not PENDING and does nothing.
            updated = (
                model.objects.filter(pk=task.pk, status=DicomTask.Status.IN_PROGRESS)
                .filter(owner_gone)
                .update(
                    status=DicomTask.Status.CANCELED,
                    message=STALE_TASK_MESSAGE,
                    end=timezone.now(),
                    queued_job_id=None,
                )
            )
            return "canceled" if updated else None

        # The WHERE re-checks status and owner inside the UPDATE itself, so nothing
        # happens if a live worker or another sweep got to this task first. The link to
        # the old row is kept: if that row runs the task again, the next sweep must see
        # who owns it — a missing link reads as "owner gone" and would reset a healthy run.
        updated = (
            model.objects.filter(pk=task.pk, status=DicomTask.Status.IN_PROGRESS)
            .filter(owner_gone)
            .update(status=DicomTask.Status.PENDING, message=STALE_TASK_MESSAGE, end=None)
        )
        if not updated:
            return None

        # Re-queue only if the old row will not run again. Read the DB fresh, not our
        # candidate snapshot: the row may have been deleted since we selected the task.
        row_alive = (
            old_row_id is not None
            and ProcrastinateJob.objects.filter(
                pk=old_row_id, status__in=_LIVE_ROW_STATUSES
            ).exists()
        )
        if not row_alive:
            model.objects.filter(pk=task.pk).update(queued_job_id=None)
            task.refresh_from_db()  # queue_pending_task() saves the whole task
            task.queue_pending_task()

    return "pending"
```

- [ ] **Step 4: Run the whole recovery test file to verify everything passes**

Run: `uv run cli test -- adit/core/tests/utils/test_recovery.py -v`
Expected: all PASS (the fresh-read test, rollback test, and canceling tests must still
pass — the canceled branch still nulls the link, the fresh read still happens after the
reset UPDATE, and `queue_pending_task()` still runs inside the transaction after the link
is cleared, so its `assert self.queued_job is None` holds).

- [ ] **Step 5: Lint and commit**

```bash
uv run cli lint
git add adit/core/utils/recovery.py adit/core/tests/utils/test_recovery.py
git commit -m "Keep the task's link to a queue row the sweep leaves alive"
```

---

### Task 2: Claim stamps the delivering queue row onto the task (9a, claim side)

**Files:**
- Modify: `adit/core/tasks.py` (claim UPDATE in `_run_dicom_task`, lines 80–96)
- Test: `adit/core/tests/test_tasks.py`

**Interfaces:**
- Consumes: nothing from Task 1 (independent change; both close different halves of 9a).
- Produces: the claim UPDATE additionally sets `queued_job_id=context.job.id`. The test
  helper `_make_context(attempts: int = 0) -> JobContext` now creates a real
  `ProcrastinateJob` row and exposes its id as `context.job.id`; test_tasks.py gains a
  module-level autouse fixture `writable_procrastinate`.

**Why the claim side is needed even with Task 1:** a task can legitimately be `PENDING`
while pointing at a *different* row than the one that ends up running it (example: worker
dies, user cancels, sweep sets the task CANCELED and clears the link, user resumes → task
is PENDING with a fresh row B; then the dead worker's old row A is retried and claims
first). Without the stamp the task runs under row A while pointing at row B — and row B
sitting in `todo` matches the sweep's "nobody is running the row" condition, so the sweep
would reset the healthy run again. The stamp makes the task always name the row that
actually claimed it; it also makes Kill work on recovered runs (Kill aborts via
`task.queued_job`).

- [ ] **Step 1: Make `_make_context` provide a real delivering row**

`queued_job_id` is a real foreign key to `procrastinate_jobs`, so the stamped id must
exist. In `adit/core/tests/test_tasks.py`:

Add near the top of the file (after the imports; `ProcrastinateJob` is already imported):

```python
@pytest.fixture(autouse=True)
def writable_procrastinate(settings):
    # Procrastinate's Django models are read-only by default; these tests create rows.
    settings.PROCRASTINATE_READONLY_MODELS = False
```

Replace the whole `_make_context` helper (lines 282–286) with:

```python
def _make_context(attempts: int = 0) -> JobContext:
    # The claim stamps context.job.id onto the task, so the row must really exist.
    row = ProcrastinateJob.objects.create(
        queue_name="dicom",
        task_name="adit.core.tasks.process_dicom_task",
        priority=0,
        args={},
        status="doing",
        attempts=attempts,
        abort_requested=False,
    )
    job = SimpleNamespace(attempts=attempts, id=row.pk)
    # _run_dicom_task only reads context.job.attempts, context.job.id and
    # context.should_abort(); a SimpleNamespace duck-types those.
    return cast(JobContext, SimpleNamespace(job=job, should_abort=lambda: False))
```

- [ ] **Step 2: Write the failing test**

Add to `adit/core/tests/test_tasks.py`, next to the other direct `_run_dicom_task` tests
(after `test_run_dicom_task_claim_increments_attempts_and_sets_start`):

```python
@pytest.mark.django_db(transaction=True)
def test_run_dicom_task_claim_stamps_the_delivering_row(mocker: MockerFixture):
    # A task revived after a crash can be claimed by a row it no longer points to. The
    # claim must record that row, so the sweep sees a live owner and Kill can abort it.
    dicom_job = ExampleTransferJobFactory.create(status=DicomJob.Status.IN_PROGRESS)
    dicom_task = ExampleTransferTaskFactory.create(
        status=DicomTask.Status.PENDING, job=dicom_job, queued_job=None
    )
    model_label = get_model_label(ExampleTransferTask)

    result: ProcessingResult = {
        "status": DicomTask.Status.SUCCESS,
        "message": "All good",
        "log": "",
    }
    _install_pebble_stubs(mocker, future=_FakeFuture(result=result))

    context = _make_context()
    tasks_module._run_dicom_task(context, model_label, dicom_task.pk)

    dicom_task.refresh_from_db()
    assert dicom_task.status == DicomTask.Status.SUCCESS
    assert dicom_task.queued_job_id == context.job.id
```

(`context.job` is typed as `Job | None`; if pyright complains about `.id`, add
`assert context.job` before the call, matching `_run_dicom_task`'s own first line.)

- [ ] **Step 3: Run the new test to verify it fails**

Run:
`uv run cli test -- adit/core/tests/test_tasks.py::test_run_dicom_task_claim_stamps_the_delivering_row -v`
Expected: FAIL at `assert dicom_task.queued_job_id == context.job.id`
(`queued_job_id` is `None`).

- [ ] **Step 4: Add the stamp to the claim UPDATE**

In `adit/core/tasks.py`, the claim currently reads (lines 76–88):

```python
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
```

Replace with:

```python
    # Claim the task with one UPDATE. Procrastinate delivers at least once, so a row can
    # arrive after another run already claimed or finished this task; then we do nothing
    # and let the row finish. A task left IN_PROGRESS by a killed worker is put back to
    # PENDING by the stale task sweep (adit/core/utils/recovery.py).
    # The claim also records which queue row runs the task: a revived task may be claimed
    # by a row it no longer points to, and the sweep and the Kill action both need the
    # real owner.
    claimed = (
        type(dicom_task)
        .objects.filter(pk=task_id, status=DicomTask.Status.PENDING)
        .update(
            status=DicomTask.Status.IN_PROGRESS,
            start=timezone.now(),
            attempts=F("attempts") + 1,
            queued_job_id=context.job.id,
        )
    )
```

- [ ] **Step 5: Run the full test_tasks.py file**

Run: `uv run cli test -- adit/core/tests/test_tasks.py -v`
Expected: all PASS. Every direct `_run_dicom_task` test now creates a real row via
`_make_context`; if any test asserts on `ProcrastinateJob` counts or on `queued_job`
being `None` after a run, read the failure and adjust that assertion to the new invariant
(a finished task keeps the stamp until Procrastinate deletes the row, which nulls the link
via the DB-level ON DELETE SET NULL).

- [ ] **Step 6: Lint and commit**

```bash
uv run cli lint
git add adit/core/tasks.py adit/core/tests/test_tasks.py
git commit -m "Stamp the delivering queue row onto the task at claim time"
```

---

### Task 3: Isolate every entry of the sweep loop (9b)

**Files:**
- Modify: `adit/core/utils/recovery.py` (function `sweep_stale_dicom_tasks`, lines 105–151)
- Test: `adit/core/tests/utils/test_recovery.py`

**Interfaces:**
- Consumes: `_resolve_stale_task` exactly as Task 1 left it (same signature; raising is
  possible when `queue_pending_task()` fails).
- Produces: `sweep_stale_dicom_tasks()` still returns `None`, but now raises
  `RuntimeError` at the very end when one or more entries failed, after processing all
  other entries. Callers already tolerate this: the management command wraps the call in
  try/except, and a failed periodic run just shows as failed and the next cron tick runs
  anyway.

- [ ] **Step 1: Write the two failing tests**

Add to `adit/core/tests/utils/test_recovery.py`. Also extend the imports: the second test
needs `ExampleTransferJob` — change the existing import line
`from ..example_app.models import ExampleTransferTask` to
`from ..example_app.models import ExampleTransferJob, ExampleTransferTask`.

```python
@pytest.mark.django_db
def test_sweep_repairs_remaining_tasks_when_one_repair_fails():
    broken = make_stale_task(DicomJob.Status.IN_PROGRESS, row=None)
    mass_job = MassTransferJobFactory.create(status=DicomJob.Status.IN_PROGRESS)
    healthy = MassTransferTaskFactory.create(
        job=mass_job, status=DicomTask.Status.IN_PROGRESS, queued_job=None
    )

    with patch.object(
        ExampleTransferTask, "queue_pending_task", autospec=True, side_effect=RuntimeError("db")
    ):
        with pytest.raises(RuntimeError, match="1 error"):
            recovery.sweep_stale_dicom_tasks()

    broken.refresh_from_db()
    healthy.refresh_from_db()
    mass_job.refresh_from_db()
    assert broken.status == DicomTask.Status.IN_PROGRESS  # rolled back; next tick retries
    assert healthy.status == DicomTask.Status.PENDING
    assert mass_job.status == DicomJob.Status.PENDING


@pytest.mark.django_db
def test_sweep_reevaluates_remaining_jobs_when_one_recount_fails():
    broken_task = make_stale_task(DicomJob.Status.CANCELING, row=None)
    healthy_task = make_stale_task(DicomJob.Status.CANCELING, row=None)
    real_post_process = ExampleTransferJob.post_process

    def failing_post_process(self, *args, **kwargs):
        if self.pk == broken_task.job.pk:
            raise RuntimeError("mail bounced")
        return real_post_process(self, *args, **kwargs)

    with patch.object(
        ExampleTransferJob, "post_process", autospec=True, side_effect=failing_post_process
    ):
        with pytest.raises(RuntimeError, match="1 error"):
            recovery.sweep_stale_dicom_tasks()

    broken_task.refresh_from_db()
    healthy_task.refresh_from_db()
    broken_task.job.refresh_from_db()
    healthy_task.job.refresh_from_db()
    assert broken_task.status == DicomTask.Status.CANCELED
    assert healthy_task.status == DicomTask.Status.CANCELED
    # The broken job keeps its old status until something re-evaluates it (documented
    # residual: its tasks are repaired, so no later sweep tick revisits it by itself).
    assert broken_task.job.status == DicomJob.Status.CANCELING
    assert healthy_task.job.status == DicomJob.Status.CANCELED
```

- [ ] **Step 2: Run them to verify they fail the right way**

Run:
`uv run cli test -- adit/core/tests/utils/test_recovery.py -k "one_repair_fails or one_recount_fails" -v`
Expected: both FAIL. The first: `pytest.raises` catches the raw `RuntimeError("db")` but
the match `"1 error"` does not match `"db"`. The second: whichever job the loop recounts
first determines the failure — either the raw `"mail bounced"` error escapes (match
fails), or the healthy job was never recounted and stays `CANCELING`.

- [ ] **Step 3: Add per-entry isolation and the summary error**

In `adit/core/utils/recovery.py`, replace the whole function `sweep_stale_dicom_tasks`
with:

```python
def sweep_stale_dicom_tasks() -> None:
    """Repair tasks left IN_PROGRESS by a killed worker, across all DicomTask models."""
    cutoff = timezone.now() - timedelta(seconds=settings.DICOM_TASK_STALLED_WORKER_GRACE_SECONDS)
    owner_gone = _owner_gone_q(cutoff)

    summary: list[str] = []
    repaired_total = 0
    errors = 0
    affected_jobs: dict[tuple[str, int], DicomJob] = {}

    for model in dicom_task_models():
        pending = canceled = 0
        candidates = (
            model.objects.filter(status=DicomTask.Status.IN_PROGRESS)
            .filter(owner_gone)
            .select_related("job", "queued_job", "queued_job__worker")
        )
        for task in candidates:
            # One broken repair must not stop the sweep; the task stays IN_PROGRESS
            # (the reset rolls back) and the next run tries it again.
            try:
                outcome = _resolve_stale_task(task, owner_gone)
            except Exception:
                logger.exception("Stale task sweep failed to repair %s.", task)
                errors += 1
                continue
            if outcome == "pending":
                pending += 1
            elif outcome == "canceled":
                canceled += 1
            else:
                continue
            affected_jobs[(task.job._meta.label, task.job.pk)] = task.job

        repaired_total += pending + canceled
        total = pending + canceled
        summary.append(f"{model.__name__} {total} ({pending} pending, {canceled} canceled)")

    for job in affected_jobs.values():
        # Recompute the job from its tasks, under the same lock the task finalizer uses.
        # A finished job is recomputed too if it still has open tasks: a repaired task
        # must never hang under a job that already reports a final result.
        # One failing recount must not stop the recounts of the other jobs.
        try:
            with pglock.advisory(DICOM_JOB_POST_PROCESS_LOCK):
                job.refresh_from_db()
                has_open_tasks = job.tasks.filter(
                    status__in=(DicomTask.Status.PENDING, DicomTask.Status.IN_PROGRESS)
                ).exists()
                if job.status not in _TERMINAL_JOB_STATUSES or has_open_tasks:
                    job.post_process()
        except Exception:
            logger.exception("Stale task sweep failed to re-evaluate %s.", job)
            errors += 1

    message = "Stale dicom task sweep: " + ", ".join(summary)
    if repaired_total:
        logger.info(message)
    else:
        logger.debug(message)

    if errors:
        raise RuntimeError(f"Stale dicom task sweep hit {errors} error(s), see logs.")
```

- [ ] **Step 4: Run the whole recovery test file and the management command tests**

Run: `uv run cli test -- adit/core/tests/utils/test_recovery.py adit/core/tests/test_management.py -v`
Expected: all PASS (the command tests must still pass — the command catches every
exception and never exits non-zero).

- [ ] **Step 5: Lint and commit**

```bash
uv run cli lint
git add adit/core/utils/recovery.py adit/core/tests/utils/test_recovery.py
git commit -m "Keep sweeping when one task repair or job recount fails"
```

---

### Task 4: Update the docs and the spec

**Files:**
- Modify: `AGENTS.md` (section "Worker Crash Recovery"; do NOT touch the `CLAUDE.md` /
  `GEMINI.md` symlinks)
- Modify: `docs/superpowers/specs/2026-08-17-worker-crash-task-recovery-design.md`

**Interfaces:**
- Consumes: the behavior shipped in Tasks 1–3.
- Produces: docs that describe the code as it now is.

- [ ] **Step 1: Update AGENTS.md**

In the "Worker Crash Recovery" section of `AGENTS.md`:

1. In the sweep paragraph, after the sentence describing the conditional UPDATE and
   re-queue, adjust it to say the link is kept when the old row is left to run again.
   Replace the sentence
   `every `IN_PROGRESS` task whose queue row is gone, finished, or owned by a worker silent for `DICOM_TASK_STALLED_WORKER_GRACE_SECONDS` (default 30, never lower) is put back to `PENDING` (or `CANCELED` if the job is canceling) with one conditional UPDATE and re-queued if its old row will not run again; affected jobs are re-evaluated with `post_process()`.`
   with:
   `every `IN_PROGRESS` task whose queue row is gone, finished, or owned by a worker silent for `DICOM_TASK_STALLED_WORKER_GRACE_SECONDS` (default 30, never lower) is put back to `PENDING` (or `CANCELED` if the job is canceling) with one conditional UPDATE. If the old queue row will not run again the task is re-queued; otherwise the task keeps pointing at that row, so later sweeps recognize the run it starts. Each repair and each job re-evaluation (`post_process()`) is isolated: one failure is logged and the sweep continues, reporting one summary error at the end.`

2. Replace the `_run_dicom_task` paragraph
   ``_run_dicom_task` claims a task with a single `PENDING → IN_PROGRESS` UPDATE and skips the delivery otherwise — Procrastinate delivers at least once, so a row may arrive for a task another run already handled.`
   with:
   ``_run_dicom_task` claims a task with a single `PENDING → IN_PROGRESS` UPDATE that also stamps the delivering queue row onto `queued_job`, and skips the delivery otherwise — Procrastinate delivers at least once, so a row may arrive for a task another run already handled.`

3. In the "Accepted:" paragraph, delete the clause
   `a task revived while its old queue row is still alive re-runs without a `queued_job` link, so Kill/Cancel cannot abort that run (it settles when the run ends) and the re-run waits for `retry_stalled_jobs` (up to 10 min)`
   and replace it with:
   `a task revived while its old queue row is still alive waits for `retry_stalled_jobs` to run that row again (up to 10 min); a job whose re-evaluation fails during a sweep keeps its stale status until a later action touches it`.

4. In the Kill row of the task actions table, the sentence "If the worker is already dead,
   the stale task sweep repairs the task" still holds — leave it.

- [ ] **Step 2: Update the spec**

In `docs/superpowers/specs/2026-08-17-worker-crash-task-recovery-design.md` (read it
first — section numbers below refer to its structure):

1. In the sweep-core section describing the conditional UPDATE, change the description so
   the PENDING reset does not clear `queued_job`; the link is cleared only in the
   not-alive branch right before re-queueing, and the CANCELED branch always clears it
   (reason: Resume requires a cleared link on CANCELED→PENDING tasks). Add the reason from
   the RADIS notes: a kept link is what stops the next sweep tick from resetting the
   healthy recovered run ("the sweep must not erase its own evidence").
2. In the claim section, document that the claim UPDATE stamps `queued_job_id` with the
   delivering row's id, and why (the task always names its true owner; Kill works on
   recovered runs; a stale second row in `todo` no longer makes the sweep reset a healthy
   run).
3. In the accepted-risks section, remove the "recovered run is unkillable until it ends"
   item (fixed by the stamp) and add: "a job whose `post_process()` fails during a sweep
   keeps its stale status; its tasks are already repaired, so no later tick revisits it
   unless another of its tasks goes stale (mitigated: ADIT saves the job status before
   sending the finished mail, so a bounced mail cannot cause this)".
4. In the follow-ups section, mark the "claim should re-link `queued_job`" item as done on
   this branch.

- [ ] **Step 3: Verify docs build nothing (no test), lint, and commit**

```bash
uv run cli lint
git add AGENTS.md docs/superpowers/specs/2026-08-17-worker-crash-task-recovery-design.md
git commit -m "Document the kept queue-row link and the isolated sweep loop"
```

---

## Final verification (after all tasks)

- [ ] Run the touched modules end to end:
  `uv run cli test -- adit/core/tests/utils/test_recovery.py adit/core/tests/test_tasks.py adit/core/tests/test_management.py -v`
  Expected: all PASS.
- [ ] Run `uv run cli lint` — clean.
- [ ] Do NOT push. Report completion to the user.
