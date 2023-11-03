# Generated by Django 4.2.4 on 2023-09-03 21:18

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0007_dicom_node_institute_access"),
        ("batch_query", "0021_set_source_in_tasks"),
    ]

    operations = [
        migrations.AlterField(
            model_name="batchquerytask",
            name="source",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="+", to="core.dicomnode"
            ),
        ),
    ]