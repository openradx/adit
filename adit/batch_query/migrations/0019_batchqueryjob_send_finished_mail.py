# Generated by Django 4.2.3 on 2023-07-31 21:08

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("batch_query", "0018_alter_batchquerytask_unique_together_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="batchqueryjob",
            name="send_finished_mail",
            field=models.BooleanField(default=False),
        ),
    ]
