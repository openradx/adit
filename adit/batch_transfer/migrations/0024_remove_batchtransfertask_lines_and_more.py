# Generated by Django 4.2.5 on 2023-10-23 12:25

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("batch_transfer", "0023_text_to_array_field"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="batchtransfertask",
            name="lines",
        ),
        migrations.RemoveField(
            model_name="batchtransfertask",
            name="series_uids",
        ),
    ]