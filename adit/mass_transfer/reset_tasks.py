"""Find and reset mass transfer tasks that produced 0-byte NIfTI files.

Background: Disk space ran out during a mass transfer job. dcm2niix wrote to a temp
folder that had space, but silently produced 0-byte .nii.gz files when writing to the
(full) destination folder. These tasks appear as SUCCESS/WARNING but the output is bad.

Usage: Run inside the Django shell (e.g. `uv run cli shell`) then:
    exec(open("adit/mass_transfer/reset_tasks.py").read())
"""

from datetime import datetime
from pathlib import Path

from django.db.models import Count
from django.utils.timezone import make_aware

from adit.core.models import DicomTask
from adit.core.utils.model_utils import reset_tasks
from adit.mass_transfer.models import MassTransferTask, MassTransferVolume

# ── Configuration ──────────────────────────────────────────────────────────────
JOB_ID = 3  # <-- set your job ID here
DISK_FULL_DATE = make_aware(datetime(2026, 4, 18))  # <-- date the disk got full
DRY_RUN = True  # <-- set to False to actually reset
# ───────────────────────────────────────────────────────────────────────────────

# 1. Overview: task status counts for this job
print(f"\n=== Job {JOB_ID} task status overview ===")
status_counts = (
    MassTransferTask.objects.filter(job_id=JOB_ID)
    .values("status")
    .annotate(count=Count("id"))
    .order_by("status")
)
for row in status_counts:
    label = DicomTask.Status(row["status"]).label
    print(f"  {label}: {row['count']}")

# 2. Find "converted" volumes on tasks that ended after the disk-full date with 0-byte files
affected_volumes = MassTransferVolume.objects.filter(
    job_id=JOB_ID,
    status=MassTransferVolume.Status.CONVERTED,
    task__end__gte=DISK_FULL_DATE,
).select_related("task")

zero_byte_volumes = []
for vol in affected_volumes:
    if not vol.converted_file:
        continue
    paths = vol.converted_file.strip().splitlines()
    for p in paths:
        filepath = Path(p.strip())
        if filepath.exists() and filepath.stat().st_size == 0:
            zero_byte_volumes.append(vol)
            break

print(f"\n=== Volumes with 0-byte NIfTI files (after {DISK_FULL_DATE.date()}) ===")
print(f"Found {len(zero_byte_volumes)} affected volumes out of {affected_volumes.count()} checked")

# 3. Collect the affected tasks
affected_task_ids = {vol.task_id for vol in zero_byte_volumes if vol.task_id}
affected_tasks = MassTransferTask.objects.filter(id__in=affected_task_ids)

print("\n=== Affected tasks ===")
print(f"Found {affected_tasks.count()} tasks to reset")
for task in affected_tasks.order_by("end"):
    total_vols = task.volumes.count()
    bad_vols = sum(1 for v in zero_byte_volumes if v.task_id == task.pk)
    print(
        f"  Task {task.pk}: {bad_vols}/{total_vols} bad volumes"
        f" | status={task.get_status_display()} | ended={task.end}"
    )

# 4. Reset and re-queue affected tasks (job stays as-is, it's still running).
# reset_tasks() sets status to PENDING and clears timing/log fields.
# queue_pending_task() enqueues the task on the Procrastinate worker.
# The processor will delete the partition folder from disk and all volumes
# for that partition before re-processing (see processors.py:287-296).
if not DRY_RUN and affected_task_ids:
    reset_tasks(affected_tasks)

    for task in MassTransferTask.objects.filter(id__in=affected_task_ids):
        task.queue_pending_task()

    print(f"\n=== Reset and re-queued {len(affected_task_ids)} tasks ===")
else:
    if affected_task_ids:
        print(f"\n=== DRY RUN — set DRY_RUN = False to reset {len(affected_task_ids)} tasks ===")
    else:
        print("\n=== No tasks to reset ===")
