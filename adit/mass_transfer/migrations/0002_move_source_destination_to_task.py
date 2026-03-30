"""Move source/destination from MassTransferJob to MassTransferTask.

MassTransferTask now inherits from TransferTask (which provides source,
destination, patient_id, study_uid, series_uids, pseudonym) instead of
DicomTask.
"""

import django.contrib.postgres.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0016_add_max_search_results_to_dicomserver"),
        ("mass_transfer", "0001_initial"),
    ]

    operations = [
        # Add new fields from TransferTask to MassTransferTask
        migrations.AddField(
            model_name="masstransfertask",
            name="destination",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="core.dicomnode",
                default=1,  # placeholder for existing rows
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="masstransfertask",
            name="patient_id",
            field=models.CharField(default="", max_length=64),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="masstransfertask",
            name="study_uid",
            field=models.CharField(default="", max_length=64),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="masstransfertask",
            name="series_uids",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=64),
                blank=True,
                default=list,
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="masstransfertask",
            name="pseudonym",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        # Remove source and destination from MassTransferJob
        migrations.RemoveField(
            model_name="masstransferjob",
            name="source",
        ),
        migrations.RemoveField(
            model_name="masstransferjob",
            name="destination",
        ),
    ]
