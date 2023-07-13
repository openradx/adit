# type: ignore

import pytest
from django_test_migrations.migrator import Migrator

from ..factories import SelectiveTransferJobFactory


@pytest.mark.django_db
def test_0012_convert_json_to_text(migrator: Migrator):
    old_state = migrator.apply_initial_migration(
        ("selective_transfer", "0011_alter_selectivetransfertask_series_uids")
    )
    SelectiveTransferTask = old_state.apps.get_model("selective_transfer", "SelectiveTransferTask")

    job = SelectiveTransferJobFactory.create()
    task = SelectiveTransferTask.objects.create(
        job_id=job.id,
        task_id="123",
        patient_id="12345",
        study_uid="1.2.3",
        series_uids='["4.5.6", "7.8.9"]',
    )

    new_state = migrator.apply_tested_migration(("selective_transfer", "0012_convert_json_to_text"))
    SelectiveTransferTask = new_state.apps.get_model("selective_transfer", "SelectiveTransferTask")

    task = SelectiveTransferTask.objects.get(id=task.id)

    assert task.series_uids == "4.5.6, 7.8.9"
