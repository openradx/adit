# Generated by Django 4.2.5 on 2023-10-24 12:34

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("batch_transfer", "0025_rename_lines_new_batchtransfertask_lines_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="batchtransfertask",
            name="series_uids",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=64), blank=True, default=list, size=None
            ),
        ),
    ]
