# Mass Transfer: Continue Past Dead Volumes on the Final Task Attempt

**Date:** 2026-06-12
**Status:** Approved

## Problem

A mass transfer task (one partition) processes its volumes (series) sequentially. When a
single volume exhausts the stamina network retries, the resulting `RetriableDicomError` is
re-raised from `_transfer_single_series` (`adit/mass_transfer/processors.py:588-591`),
aborting the entire task. Procrastinate retries the whole task up to
`DICOM_TASK_MAX_ATTEMPTS` (default 3); each retry wipes and re-fetches the whole partition
and hits the same dead series again. After the final attempt the task is marked `FAILURE`,
even when only 1-2 of its volumes are actually unrecoverable (e.g. series on
archived/offline PACS storage).

There is no way to exclude specific series: volumes are ephemeral — every task run deletes
all `MassTransferVolume` rows for the partition and re-discovers them from the PACS
(`processors.py:341-349, 360-364`).

## Decision

Keep the existing abort-and-retry behavior on non-final attempts (a transient PACS outage
can recover during the 2-4 min Procrastinate waits). On the **final attempt only**, mark
the dead volume `ERROR` and continue with the remaining volumes, so the partition completes
as `WARNING` instead of `FAILURE`.

This was chosen over two alternatives:

- **Always continue, retry at end:** every attempt would re-fetch the entire partition
  (more PACS load) for little gain.
- **Never retry per-volume errors:** simplest, but a multi-minute PACS blip would
  permanently fail volumes that a task-level retry would have recovered.

A larger follow-up (durable volumes with per-volume retry granularity) is planned
separately; this change is forward-compatible with it and will be simplified by it.

## Design

### Behavior

- On attempts 1 to N-1 (where N = `settings.DICOM_TASK_MAX_ATTEMPTS`): unchanged. A
  per-volume `RetriableDicomError` marks the volume `ERROR` with log
  `"Transfer interrupted by retriable error; task will be retried."` and re-raises,
  triggering a task-level retry.
- On the final attempt (`mass_task.attempts >= settings.DICOM_TASK_MAX_ATTEMPTS`): the
  volume is marked `ERROR` with log
  `"Transfer failed after exhausting retries: <error>"` and the transfer loop continues
  with the remaining volumes. No exception propagates.

`DicomTask.attempts` is incremented and saved by the task runner before `process()` runs
(`adit/core/tasks.py:85-86`), so the processor subprocess reads an accurate count from the
database.

### Code changes

Single file: `adit/mass_transfer/processors.py`.

1. Add a small `_is_final_attempt()` helper on `MassTransferTaskProcessor`:
   `self.mass_task.attempts >= settings.DICOM_TASK_MAX_ATTEMPTS`.
2. Branch in the `except RetriableDicomError` handler of `_transfer_single_series`:
   re-raise only when not the final attempt; otherwise set the error log and fall through
   to the existing `finally` block (which saves the volume).

No model changes, no migration, no UI changes.

### Status outcomes (existing machinery, untouched)

- `_transfer_grouped_series` already counts `ERROR` volumes into `total_failed` and
  aggregates `failed_reasons`.
- `_build_task_summary` already yields `WARNING` for partial failure and `FAILURE` when
  all volumes failed.
- A `RetriableDicomError` raised outside the per-volume loop (e.g. during series
  discovery, before any volumes exist) still propagates and retries/fails the whole task.

### Known edge (accepted)

After cancel -> resume, `DicomTask.attempts` is not reset, so a resumed task may treat its
first resumed run as final and continue past dead volumes instead of retrying. This is a
graceful degradation and is documented in a code comment.

## Testing

New tests in `adit/mass_transfer/tests/test_processor.py`:

1. Non-final attempt: per-volume `RetriableDicomError` is re-raised; volume is `ERROR`
   with the "will be retried" log (existing behavior preserved).
2. Final attempt, one dead volume among healthy ones: no exception, task result `WARNING`,
   dead volume `ERROR` with the exhausted-retries log, other volumes `EXPORTED`.
3. Final attempt, all volumes dead: task result `FAILURE`.
4. Boundary: `attempts == DICOM_TASK_MAX_ATTEMPTS - 1` aborts (re-raises);
   `attempts == DICOM_TASK_MAX_ATTEMPTS` continues.

## Operational note: rescuing prod mass transfer job 1

After deploying, use **Retry** on the job. It resets the 3 failed tasks (`attempts=0`) and
re-queues them. Each task burns attempts 1-2 against the dead series (~6-8 min of retry
waits), then attempt 3 completes the partition as `WARNING` with only the 1-2 dead volumes
marked `ERROR`. No manual exclusion needed.
