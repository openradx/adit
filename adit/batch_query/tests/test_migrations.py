# type: ignore

import pytest
from django_test_migrations.migrator import Migrator

from ..factories import BatchQueryJobFactory


@pytest.mark.django_db
def test_0016_convert_json_to_text(migrator: Migrator):
    old_state = migrator.apply_initial_migration(
        ("batch_query", "0015_alter_batchqueryresult_modalities_and_more")
    )
    BatchQueryTask = old_state.apps.get_model("batch_query", "BatchQueryTask")
    BatchQueryResult = old_state.apps.get_model("batch_query", "BatchQueryResult")

    job = BatchQueryJobFactory.create()
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
