# Generated by Django 3.1.3 on 2021-02-16 13:26

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("batch_transfer", "0003_auto_20210128_1605"),
    ]

    operations = [
        migrations.AddField(
            model_name="batchtransfertask",
            name="celery_task_id",
            field=models.CharField(default=uuid.uuid4(), max_length=255),
            preserve_default=False,
        ),
    ]
