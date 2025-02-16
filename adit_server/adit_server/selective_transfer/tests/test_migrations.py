import pytest
from django_test_migrations.migrator import Migrator


@pytest.mark.django_db
def test_0012_convert_json_to_text(migrator_ext: Migrator):
    old_state = migrator_ext.apply_initial_migration(
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
        series_uids='["4.5.6", "7.8.9"]',
    )

    new_state = migrator_ext.apply_tested_migration(
        ("selective_transfer", "0012_convert_json_to_text")
    )
    SelectiveTransferTask = new_state.apps.get_model("selective_transfer", "SelectiveTransferTask")

    task = SelectiveTransferTask.objects.get(id=task.id)

    assert task.series_uids == "4.5.6, 7.8.9"


@pytest.mark.django_db
def test_0016_set_source_and_destination_in_tasks(migrator_ext: Migrator):
    old_state = migrator_ext.apply_initial_migration(
        ("selective_transfer", "0015_selectivetransfertask_source_and_destination")
    )

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
    )

    new_state = migrator_ext.apply_tested_migration(
        ("selective_transfer", "0016_set_source_and_destination_in_tasks")
    )
    SelectiveTransferTask = new_state.apps.get_model("selective_transfer", "SelectiveTransferTask")

    task = SelectiveTransferTask.objects.get(id=task.id)

    assert task.source.name == "server1"
    assert task.destination.name == "server2"


@pytest.mark.django_db
def test_0021_move_text_to_array_field(migrator_ext: Migrator):
    old_state = migrator_ext.apply_initial_migration(
        ("selective_transfer", "0020_selectivetransfertask_series_uids_new")
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
        owner_id=user.id,
    )
    task = SelectiveTransferTask.objects.create(
        job_id=job.id,
        source_id=server1.id,
        destination_id=server2.id,
        series_uids="4.5.6, 7.8.9",
        series_uids_new=[],
    )

    new_state = migrator_ext.apply_tested_migration(
        ("selective_transfer", "0021_text_to_array_field")
    )
    SelectiveTransferTask = new_state.apps.get_model("selective_transfer", "SelectiveTransferTask")

    task = SelectiveTransferTask.objects.get(id=task.id)

    assert task.series_uids_new == ["4.5.6", "7.8.9"]


@pytest.mark.django_db
def test_0027_switch_to_procrastinate(migrator_ext: Migrator):
    old_state = migrator_ext.apply_initial_migration(
        ("selective_transfer", "0026_remove_selectivetransfersettings_slot_begin_time_and_more")
    )

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
        owner_id=user.id,
    )
    task = SelectiveTransferTask.objects.create(
        job_id=job.id,
        source_id=server1.id,
        destination_id=server2.id,
    )

    new_state = migrator_ext.apply_tested_migration(
        ("selective_transfer", "0027_switch_to_procrastinate")
    )

    SelectiveTransferTask = new_state.apps.get_model("selective_transfer", "SelectiveTransferTask")

    assert task.retries + 1 == SelectiveTransferTask.objects.get(id=task.id).attempts
