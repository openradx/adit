# type: ignore

import pytest
from django_test_migrations.migrator import Migrator


@pytest.mark.django_db
def test_0016_convert_json_to_text(migrator: Migrator):
    old_state = migrator.apply_initial_migration(
        ("batch_query", "0015_alter_batchqueryresult_modalities_and_more")
    )

    # Historical models are reconstructed from the migration files. We can't use our factories here.
    User = old_state.apps.get_model("accounts", "User")
    DicomServer = old_state.apps.get_model("core", "DicomServer")
    BatchQueryJob = old_state.apps.get_model("batch_query", "BatchQueryJob")
    BatchQueryTask = old_state.apps.get_model("batch_query", "BatchQueryTask")
    BatchQueryResult = old_state.apps.get_model("batch_query", "BatchQueryResult")

    server1 = DicomServer.objects.create(
        ae_title="server1",
        name="server1",
        host="server1",
        port=11112,
    )
    user = User.objects.create(
        username="user",
    )
    job = BatchQueryJob.objects.create(
        source_id=server1.id,
        owner_id=user.id,
    )
    query = BatchQueryTask.objects.create(
        job_id=job.id,
        task_id="123",
        lines='["1", "2", "3"]',
        modalities='["CT", "MR"]',
        series_numbers='["4", "5", "6"]',
    )
    result = BatchQueryResult.objects.create(
        job_id=job.id,
        query_id=query.id,
        patient_id="12345",
        patient_name="Doe^John",
        patient_birth_date="1980-01-01",
        study_date="2010-01-01",
        study_time="12:00",
        modalities='["CT", "MR"]',
        study_uid="1.2.3",
    )

    new_state = migrator.apply_tested_migration(("batch_query", "0016_convert_json_to_text"))
    BatchQueryTask = new_state.apps.get_model("batch_query", "BatchQueryTask")
    BatchQueryResult = new_state.apps.get_model("batch_query", "BatchQueryResult")

    query = BatchQueryTask.objects.get(id=query.id)
    result = BatchQueryResult.objects.get(id=result.id)

    assert query.lines == "1, 2, 3"
    assert query.modalities == "CT, MR"
    assert query.series_numbers == "4, 5, 6"

    assert result.modalities == "CT, MR"
