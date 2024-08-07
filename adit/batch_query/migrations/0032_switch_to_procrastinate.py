# Generated by Django 5.0.6 on 2024-07-07 19:47

import django.db.models.deletion
from django.apps import AppConfig
from django.db import migrations, models

from adit_radis_shared.common.utils.migration_utils import procrastinate_on_delete_sql


def increase_attempt(apps: AppConfig, schema_editor):
    BatchQueryTask = apps.get_model("batch_query.BatchQueryTask")
    BatchQueryTask.objects.update(attempts=models.F("attempts") + 1)

def decrease_attempt(apps: AppConfig, schema_editor):
    BatchQueryTask = apps.get_model("batch_query.BatchQueryTask")
    BatchQueryTask.objects.update(attempts=models.F("attempts") - 1)
    

class Migration(migrations.Migration):

    dependencies = [
        ("batch_query", "0031_remove_batchquerysettings_slot_begin_time_and_more"),
        ("procrastinate", "0028_add_cancel_states"),
    ]

    operations = [
        migrations.RenameField(
            model_name="batchquerytask",
            old_name="retries",
            new_name="attempts",
        ),
        migrations.AddField(
            model_name="batchquerytask",
            name="queued_job",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="procrastinate.procrastinatejob",
            ),
        ),
        migrations.RunSQL(
            sql=procrastinate_on_delete_sql("batch_query", "batchquerytask"),
            reverse_sql=procrastinate_on_delete_sql("batch_query", "batchquerytask", reverse=True),
        ),
        migrations.RunPython(increase_attempt, decrease_attempt),
    ]
