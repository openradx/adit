# Generated by Django 4.2.7 on 2023-11-13 14:08

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("upload", "0003_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="uploadtask",
            name="job",
        ),
        migrations.RemoveField(
            model_name="uploadtask",
            name="source",
        ),
        migrations.DeleteModel(
            name="UploadJob",
        ),
        migrations.DeleteModel(
            name="UploadTask",
        ),
    ]
