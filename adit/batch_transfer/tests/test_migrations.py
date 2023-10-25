# type: ignore

import pytest
from django_test_migrations.migrator import Migrator


@pytest.mark.django_db
def test_0013_convert_json_to_text(migrator: Migrator):
    old_state = migrator.apply_initial_migration(
        ("batch_transfer", "0012_alter_batchtransfertask_lines_and_more")
    )

    # Historical models are reconstructed from the migration files. We can't use our factories here.
    User = old_state.apps.get_model("accounts", "User")
    DicomServer = old_state.apps.get_model("core", "DicomServer")
    BatchTransferJob = old_state.apps.get_model("batch_transfer", "BatchTransferJob")
    BatchTransferTask = old_state.apps.get_model("batch_transfer", "BatchTransferTask")

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
    job = BatchTransferJob.objects.create(
        source_id=server1.id,
        destination_id=server2.id,
        owner_id=user.id,
    )
    task = BatchTransferTask.objects.create(
        job_id=job.id,
        task_id="123",
        lines='["1", "2", "3"]',
        series_uids='["4.5.6", "7.8.9"]',
    )

    new_state = migrator.apply_tested_migration(("batch_transfer", "0013_convert_json_to_text"))
    BatchTransferTask = new_state.apps.get_model("batch_transfer", "BatchTransferTask")

    task = BatchTransferTask.objects.get(id=task.id)

    assert task.lines == "1, 2, 3"
    assert task.series_uids == "4.5.6, 7.8.9"


@pytest.mark.django_db
def test_0018_set_source_and_destination_in_tasks(migrator: Migrator):
    old_state = migrator.apply_initial_migration(
        ("batch_transfer", "0017_batchtransfertask_source_and_destination")
    )

    User = old_state.apps.get_model("accounts", "User")
    DicomServer = old_state.apps.get_model("core", "DicomServer")
    BatchTransferJob = old_state.apps.get_model("batch_transfer", "BatchTransferJob")
    BatchTransferTask = old_state.apps.get_model("batch_transfer", "BatchTransferTask")

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
    job = BatchTransferJob.objects.create(
        source_id=server1.id,
        destination_id=server2.id,
        owner_id=user.id,
    )
    task = BatchTransferTask.objects.create(
        job_id=job.id,
        task_id="123",
    )

    new_state = migrator.apply_tested_migration(
        ("batch_transfer", "0018_set_source_and_destination_in_tasks")
    )
    BatchTransferTask = new_state.apps.get_model("batch_transfer", "BatchTransferTask")

    task = BatchTransferTask.objects.get(id=task.id)

    assert task.source.name == "server1"
    assert task.destination.name == "server2"


@pytest.mark.django_db
def test_0023_move_text_to_array_field(migrator: Migrator):
    old_state = migrator.apply_initial_migration(
        ("batch_transfer", "0022_batchtransfertask_lines_new_and_more")
    )

    # Historical models are reconstructed from the migration files. We can't use our factories here.
    User = old_state.apps.get_model("accounts", "User")
    DicomServer = old_state.apps.get_model("core", "DicomServer")
    BatchTransferJob = old_state.apps.get_model("batch_transfer", "BatchTransferJob")
    BatchTransferTask = old_state.apps.get_model("batch_transfer", "BatchTransferTask")

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
    job = BatchTransferJob.objects.create(
        owner_id=user.id,
    )
    task = BatchTransferTask.objects.create(
        job_id=job.id,
        source_id=server1.id,
        destination_id=server2.id,
        lines="1, 2, 3",
        lines_new=[],
        series_uids="4.5.6, 7.8.9",
        series_uids_new=[],
    )

    new_state = migrator.apply_tested_migration(("batch_transfer", "0023_text_to_array_field"))
    BatchTransferTask = new_state.apps.get_model("batch_transfer", "BatchTransferTask")

    task = BatchTransferTask.objects.get(id=task.id)

    assert task.lines_new == [1, 2, 3]
    assert task.series_uids_new == ["4.5.6", "7.8.9"]
