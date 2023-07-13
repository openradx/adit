# type: ignore

import pytest
from django_test_migrations.migrator import Migrator


@pytest.mark.django_db
def test_0012_convert_json_to_text(migrator: Migrator):
    old_state = migrator.apply_initial_migration(
        ("selective_transfer", "0011_alter_selectivetransfertask_series_uids")
    )

    # Historical models are reconstructed from the migration files. We can't use our factories here.
    User = old_state.apps.get_model("accounts", "User")
    DicomServer = old_state.apps.get_model("core", "DicomServer")
    SelectiveTransferJob = old_state.apps.get_model("selective_transfer", "SelectiveTransferJob")
    SelectiveTransferTask = old_state.apps.get_model("selective_transfer", "SelectiveTransferTask")

    server1 = DicomServer.objects.create(
        ae_title="server1",
        name="server1",
        host="server1",
        port=11112,
    )
    server2 = DicomServer.objects.create(
        ae_title="server2",
        name="server2",
        host="server2",
        port=11112,
    )
    user = User.objects.create(
        username="user",
    )
    job = SelectiveTransferJob.objects.create(
        source_id=server1.id,
        destination_id=server2.id,
        owner_id=user.id,
    )
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
