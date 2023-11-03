# Generated by Django 4.2.4 on 2023-09-03 20:54

from django.apps import AppConfig
from django.db import migrations


def set_source_and_destination_in_tasks(apps: AppConfig, schema_editor):
    SelectiveTransferJob = apps.get_model("selective_transfer.SelectiveTransferJob")
    for job in SelectiveTransferJob.objects.all():
        for task in job.tasks.all():
            task.source_id = job.source_id
            task.destination_id = job.destination_id
            task.save()


def set_source_and_destination_in_jobs(apps: AppConfig, schema_editor):
    SelectiveTransferJob = apps.get_model("selective_transfer.SelectiveTransferJob")
    for job in SelectiveTransferJob.objects.all():
        task = job.tasks.first()
        job.source_id = task.source_id
        job.destination_id = task.destination_id
        job.save()


class Migration(migrations.Migration):
    dependencies = [
        ("selective_transfer", "0015_selectivetransfertask_source_and_destination"),
    ]

    operations = [
        migrations.RunPython(
            set_source_and_destination_in_tasks, set_source_and_destination_in_jobs
        )
    ]