# Generated by Django 4.2.7 on 2023-11-08 21:53

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("batch_transfer", "0027_alter_batchtransfertask_series_uids"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="batchtransfersettings",
            name="slot_begin_time",
        ),
        migrations.RemoveField(
            model_name="batchtransfersettings",
            name="slot_end_time",
        ),
        migrations.RemoveField(
            model_name="batchtransfersettings",
            name="transfer_timeout",
        ),
        migrations.RemoveField(
            model_name="batchtransfertask",
            name="celery_task_id",
        ),
    ]