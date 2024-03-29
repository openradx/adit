# Generated by Django 4.2.2 on 2023-06-23 10:03

import json
from django.apps import AppConfig
from django.db import migrations


def convert_json_to_text(apps: AppConfig, schema_editor):
    SelectiveTransferTask = apps.get_model("selective_transfer.SelectiveTransferTask")
    for task in SelectiveTransferTask.objects.all():
        if not task.series_uids:
            task.series_uids = ""
        else:
            task.series_uids = ", ".join(json.loads(task.series_uids))

        task.save()


def convert_text_to_json(apps: AppConfig, schema_editor):
    SelectiveTransferTask = apps.get_model("selective_transfer.SelectiveTransferTask")
    for task in SelectiveTransferTask.objects.all():
        if not task.series_uids:
            task.series_uids = "null"
        else:
            task.series_uids = json.dumps(list(map(str.strip, task.series_uids.split(","))))

        task.save()


class Migration(migrations.Migration):
    dependencies = [
        ("selective_transfer", "0011_alter_selectivetransfertask_series_uids"),
    ]

    operations = [migrations.RunPython(convert_json_to_text, convert_text_to_json)]
