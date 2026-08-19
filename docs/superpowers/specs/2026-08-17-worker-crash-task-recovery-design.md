# Worker-crash task recovery — design

Date: 2026-08-17
Status: approved in brainstorm, awaiting spec review
Reference: RADIS PR [openradx/radis#276](https://github.com/openradx/radis/pull/276) and
`docs/superpowers/notes/2026-08-17-worker-crash-recovery-handoff-from-radis.md`

## 1. Problem

Two layers hold state for a running DICOM task and they heal independently:

- **Queue rows** (`procrastinate_jobs`): `todo → doing → succeeded/failed`, deleted on
  finish. Healed by Procrastinate plus the shared `retry_stalled_jobs` (periodic every
  10 min and at web boot): a `doing` row whose worker heartbeat is >30 s stale goes back
  to `todo` and is re-delivered.
- **Task rows** (`DicomTask` subclasses): `PENDING → IN_PROGRESS → SUCCESS/WARNING/
  FAILURE/CANCELED`. Only app code running inside a fired task moves them.

When a worker is killed mid-task the task row stays `IN_PROGRESS`. Today
`_run_dicom_task` tolerates an `IN_PROGRESS` task on re-delivery
(`assert status in (PENDING, IN_PROGRESS)`), so the common case recovers via
`retry_stalled_jobs`. Nothing repairs a task that is `IN_PROGRESS` **without a live
queue row**:

- **Kill** on a task whose worker is already dead: the row is aborted, the re-delivered
  row aborts immediately, but if delivery never happens (row gone) the task stays
  `IN_PROGRESS` and the job hangs `IN_PROGRESS`/`CANCELING` with no UI escape.
- A re-delivered row that dies before reaching the status write, or a row that fails out
  for good, leaves the same orphan.
- The tolerant `assert` is still an at-least-once hazard: it is written for
  exactly-once delivery and `python -O` strips it.

## 2. Decisions taken in the brainstorm

| Decision | Choice | Why |
|---|---|---|
| Recovery mechanism | Periodic sweep + boot-time sweep, as in RADIS | Nothing else repairs task rows; boot covers "all workers died", periodic covers steady state |
| Task claim | Strict CAS: `PENDING → IN_PROGRESS` only; 0 rows → warn and return | Single-owner semantics; a stale `IN_PROGRESS` task is repaired by the sweep within one interval |
| Code location | ADIT-local `adit/core/utils/recovery.py` | No cross-repo release; move into `adit-radis-shared` later once both copies have settled |
| Revive cap | None — always revive | Same as RADIS; a task that repeatedly kills its worker cycles until canceled; `DicomTask.attempts` keeps counting and is visible in the UI |
| Scope | `IN_PROGRESS` tasks only | `PENDING` tasks with no queue row are a different failure class (see §8) |

## 3. Sweep core — `adit/core/utils/recovery.py`

### Task models
`_dicom_task_models()` returns every concrete subclass of `DicomTask` via
`apps.get_models()` (currently selective_transfer, batch_transfer, batch_query,
mass_transfer). No hardcoded list.

### Owner-gone predicate
`_owner_gone_q(cutoff)` is an OR of positive conditions (an `.exclude()` over the
nullable join would drop tasks with no row at all):

- `queued_job` is NULL (row deleted; workers run with `--delete-jobs=always`)
- row status is not `doing` (`todo`, `succeeded`, `failed`, `cancelled`, `aborted`)
- row is `doing` but its worker row no longer exists
- row is `doing` but `worker.last_heartbeat < cutoff`

`cutoff = now − DICOM_TASK_STALLED_WORKER_GRACE_SECONDS` (default 30). A task that
runs for hours in its pebble subprocess is *not* stale: the parent worker keeps
heartbeating.

### Resolve one stale task
`_resolve_stale_task(task)`, all inside one `transaction.atomic()`:

1. Target status: `CANCELED` (with `end=now`) if the job is `CANCELING` or `CANCELED`,
   else `PENDING` (with `end=None`).
2. Conditional UPDATE:
   `Model.objects.filter(pk, status=IN_PROGRESS).filter(owner_gone).update(status=target,
   message="The worker processing this task was terminated.", end=…, queued_job_id=None)`.
   0 rows → another sweep or a live worker got there first → return `None`.
   `attempts` is left untouched.
3. If target is `PENDING`: fresh query — is the old row still `todo`/`doing`? If yes,
   `retry_stalled_jobs` will re-deliver it; do not create a second row. If no,
   `task.refresh_from_db(); task.queue_pending_task()` — the model's own method picks
   the right task function and queue (`process_dicom_task`/`dicom` or
   `process_mass_transfer_task`/`mass_transfer`).

Reset and re-queue share the transaction so a failed `defer()` rolls the task back to
`IN_PROGRESS` for the next tick; a `PENDING` task without a row would otherwise be
invisible forever. Procrastinate's Django connector defers on Django's connection, so
`atomic()` covers the row insert.

### Sweep
`sweep_stale_dicom_tasks()`:

- per model: select `IN_PROGRESS` + owner_gone with
  `select_related("job", "queued_job", "queued_job__worker")`, resolve each, collect
  affected jobs;
- for each affected job: `refresh_from_db()`, then `post_process()` under
  `pglock.advisory(DISTRIBUTED_LOCK)` (the same lock the task finalizer in
  `adit/core/tasks.py` uses). Terminal jobs are re-evaluated too if they still have
  `PENDING`/`IN_PROGRESS` tasks;
- one summary log line; INFO only if something was repaired, DEBUG otherwise.

## 4. Task claim — `adit/core/tasks.py::_run_dicom_task`

Replace the tolerant assert with one conditional UPDATE:

```python
claimed = type(dicom_task).objects.filter(pk=task_id, status=PENDING).update(
    status=IN_PROGRESS, start=timezone.now(), attempts=F("attempts") + 1
)
if not claimed:
    logger.warning("%s is not PENDING (%s); skipping this delivery.", dicom_task, dicom_task.status)
    return
dicom_task.refresh_from_db()
```

- 0 rows: the row finishes normally and is deleted. A truly orphaned `IN_PROGRESS`
  task is repaired by the sweep; a late duplicate delivery of a `SUCCESS`/`CANCELED`
  task does nothing.
- The job flip `PENDING → IN_PROGRESS`, the pebble subprocess, monitor thread, retry
  logic and `finally` block are unchanged. `process_mass_transfer_task` inherits the
  change through `_run_dicom_task`.
- Comment style: plain what + short why ("Procrastinate delivers at least once, so a
  row can arrive after another run already claimed or finished this task; then we do
  nothing and let the row finish").

### Retry semantics are unchanged
`DICOM_TASK_MAX_ATTEMPTS` is Procrastinate's `RetryStrategy.max_attempts` on the queue
row. Between `RetriableDicomError` retries the task is `PENDING` (invisible to the sweep);
on the final attempt it is `FAILURE` (also invisible). After a sweep recovery the task
runs under a row with the same strategy — the re-delivered original row keeps its
`attempts`, a new row starts at 0 — and still fails after at most three retriable
errors on that row. `DicomTask.attempts` is a separate informational counter with no
limit.

## 5. Wiring

- **Management command** `adit/core/management/commands/sweep_stale_tasks.py`: runs
  the sweep inside `try/except Exception`, logs the exception, prints
  "failed (see logs)", always exits 0. It is chained with `&&` before `bg_worker`; a
  worker that won't boot is worse than a repair that didn't happen.
- **Periodic task** in `adit/core/tasks.py`:
  `@app.periodic(cron=settings.DICOM_TASK_SWEEP_CRON)` +
  `@app.task(queueing_lock="sweep_stale_tasks")`, on the `default` queue.
- **Compose** (`docker-compose.dev.yml`, `docker-compose.prod.yml`):
  `./manage.py sweep_stale_tasks &&` before `bg_worker` in `default_worker`,
  `dicom_worker`, `mass_transfer_worker`. `retry_stalled_jobs` stays as is (web boot +
  shared periodic): it heals rows, the sweep heals tasks.
- **Settings** (`adit/settings/base.py`, next to `STALLED_JOBS_RETRY_PRIORITY`):
  `DICOM_TASK_STALLED_WORKER_GRACE_SECONDS = env.int(..., default=30)` — comment:
  never below 30, Procrastinate declares workers stalled at 30 s; lower makes ADIT
  stricter than the queue and causes duplicate runs.
  `DICOM_TASK_SWEEP_CRON = env.str(..., default="* * * * *")`. Both in `example.env`.
- **Docs**: `AGENTS.md`/`CLAUDE.md` get a "Worker crash recovery" subsection (two-layer
  model, what the sweep repairs, accepted risks); the Kill row is corrected (row is
  aborted, not deleted, while `doing`; a dead worker's task is repaired by the sweep);
  "two queues" becomes three. `KNOWLEDGE.md` gets a short Procrastinate/recovery entry.

## 6. Races and error handling (by construction)

- **Sweep vs live worker finishing the task**: the reset UPDATE re-checks
  `status=IN_PROGRESS AND owner_gone` in its WHERE at execution time. If the worker's
  `finally` save landed first, 0 rows are updated and the sweep skips. If the sweep
  landed first, the worker's save overwrites `PENDING` with the real outcome; a
  possibly re-queued row then hits the strict claim, sees non-`PENDING`, and returns.
- **Two sweeps at once** (one worker restarts while another runs the periodic sweep, or
  several workers boot together): same conditional UPDATE; Postgres serializes the two
  UPDATEs and the loser re-evaluates its WHERE on the winner's row → 0 rows.
  `queueing_lock` additionally stops periodic runs piling up.
- **Reset ok, re-queue failed**: single transaction; rollback to `IN_PROGRESS`.
- **Row vanished between select and resolve**: row liveness is a fresh query after
  the UPDATE, not the candidate snapshot.
- **Sweep raises**: command exits 0 and logs; the periodic run fails and Procrastinate
  schedules the next one.
- **Job re-evaluation vs finishing worker**: `post_process()` under the shared advisory
  lock.

## 7. Accepted risks (documented, not solved)

1. **False-positive stall → duplicate execution.** A worker frozen ≥30 s but alive:
   the sweep resets the task; the row is still `doing` so no new row is created, but
   `retry_stalled_jobs` re-delivers it → a second run while the first may still be
   alive. The CAS cannot prevent this (the task really is `PENDING` again). Cost is
   wasted transfer work; re-sending the same instances to a PACS is idempotent at the
   destination. Requires the whole worker process frozen — heartbeats run in the
   worker's own loop, independent of the pebble subprocess.
2. **No revive cap** — see §2.
3. **Sweep vs Cancel race**: cancel lands between select and resolve → task re-queued
   `PENDING` under a `CANCELING` job → self-heals when the row fires.
4. **Grace floor documented, not enforced.**
5. **Recovered run is unkillable until it ends.** When the sweep resets a task whose old
   queue row is still alive, it clears `queued_job` and does not create a new row; the
   re-delivered row re-runs the task without re-linking `queued_job`, so Kill/Cancel
   cannot abort that run — it settles when the run finishes — and the re-run waits for
   `retry_stalled_jobs` (up to 10 min). Follow-up idea (not in this branch): have the
   claim UPDATE set `queued_job_id` from the delivering row's id.

## 8. Follow-ups (out of scope)

- `PENDING` tasks with no queue row under a `PENDING`/`IN_PROGRESS` job (Reset/Resume
  view dying between `reset_tasks()` and `queue_pending_task()`;
  `queue_mass_transfer_tasks` exhausting its retries mid-enqueue). Needs a job-status-
  aware select and a grace against racing views. Manual Restart/Reset remain the escape
  hatch.
- Move the sweep core into `adit-radis-shared` once ADIT's and RADIS's copies have
  settled.

## 9. Testing

Pytest-django with the `example_app` factories and `ProcrastinateJob`/
`ProcrastinateWorker` rows written directly (as `test_tasks.py` and
`mass_transfer/tests/test_queue_pending_tasks.py` already do). No real worker process.

`adit/core/tests/utils/test_recovery.py`:
1. Owner-gone predicate, one test per branch (no row; row `succeeded`/`failed`/`todo`;
   `doing` + no worker; `doing` + stale heartbeat) and the negatives (`doing` + fresh
   heartbeat untouched; `PENDING`/`SUCCESS` tasks untouched).
2. Reset outcome: `PENDING`, `queued_job_id=None`, message, `end=None`, `attempts`
   unchanged; under `CANCELING`/`CANCELED` job → `CANCELED` with `end` set.
3. Re-queue rule: row gone → new row linked, right task name/queue for a core task and
   for a `MassTransferTask`; row `todo`/`doing` alive → no new row.
4. Atomicity: `queue_pending_task` patched to raise → task stays `IN_PROGRESS`, no row.
5. CAS guard: task flipped to `SUCCESS` between select and resolve → 0 updated, nothing
   re-queued.
6. Job re-evaluation: `CANCELING` job drains to `CANCELED`; `IN_PROGRESS` job returns to
   `PENDING`; a `SUCCESS` job with a stray `IN_PROGRESS` task is re-evaluated.
7. Summary log INFO only when something was repaired.
8. End-to-end (DB-only): "row deleted, job stuck `IN_PROGRESS`" → one sweep → task
   `PENDING` with new row, job `PENDING`; "job stuck `CANCELING`" → task and job
   `CANCELED`, no new row.

`adit/core/tests/test_tasks.py` (extend): claim on `PENDING` runs and increments
`attempts`; claim on `IN_PROGRESS` warns and returns (flip any existing test that
asserts the old tolerant behaviour); claim on `SUCCESS` is a no-op; existing
retriable-error tests unchanged.

`adit/core/tests/test_management.py` (new): `call_command("sweep_stale_tasks")` with
the sweep patched to raise completes with exit 0 and logs the error.

Manual once before the PR: kill `dicom_worker` mid-transfer under Docker, watch the
sweep repair the task; note the result in the PR description.
