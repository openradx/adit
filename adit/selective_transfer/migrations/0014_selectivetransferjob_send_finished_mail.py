# Generated by Django 4.2.3 on 2023-07-31 21:08

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("selective_transfer", "0013_alter_selectivetransfertask_unique_together_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="selectivetransferjob",
            name="send_finished_mail",
            field=models.BooleanField(default=False),
        ),
    ]
