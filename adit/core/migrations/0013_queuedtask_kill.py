# Generated by Django 4.2.8 on 2023-12-17 16:29

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_remove_dicomnode_institutes_dicomnode_groups_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="queuedtask",
            name="kill",
            field=models.BooleanField(default=False),
        ),
    ]
