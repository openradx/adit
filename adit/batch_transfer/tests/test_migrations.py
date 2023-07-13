# type: ignore

import pytest
from django_test_migrations.migrator import Migrator

from ..factories import BatchTransferJobFactory


@pytest.mark.django_db
def test_0013_convert_json_to_text(migrator: Migrator):
    old_state = migrator.apply_initial_migration(
        ("batch_transfer", "0012_alter_batchtransfertask_lines_and_more")
    )
    BatchTransferTask = old_state.apps.get_model("batch_transfer", "BatchTransferTask")

    job = BatchTransferJobFactory.create()
    task = BatchTransferTask.objects.create(
        job_id=job.id,
        task_id="123",
        lines='["1", "2", "3"]',
        patient_id="12345",
        study_uid="1.2.3",
        series_uids='["4.5.6", "7.8.9"]',
    )

    new_state = migrator.apply_tested_migration(("batch_transfer", "0013_convert_json_to_text"))
    BatchTransferTask = new_state.apps.get_model("batch_transfer", "BatchTransferTask")

    task = BatchTransferTask.objects.get(id=task.id)

    assert task.lines == "1, 2, 3"
    assert task.series_uids == "4.5.6, 7.8.9"
