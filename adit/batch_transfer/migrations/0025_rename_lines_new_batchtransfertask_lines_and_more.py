# Generated by Django 4.2.5 on 2023-10-23 12:29

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("batch_transfer", "0024_remove_batchtransfertask_lines_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="batchtransfertask",
            old_name="lines_new",
            new_name="lines",
        ),
        migrations.RenameField(
            model_name="batchtransfertask",
            old_name="series_uids_new",
            new_name="series_uids",
        ),
    ]
