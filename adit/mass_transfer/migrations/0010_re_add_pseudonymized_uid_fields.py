# Re-add pseudonymized UID fields that were removed in 0009.
# Migration 0009 (remove_pseudonymized_uid_fields) removed these columns.
# This migration adds them back.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mass_transfer', '0009_remove_pseudonymized_uid_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='masstransfervolume',
            name='study_instance_uid_pseudonymized',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
        migrations.AddField(
            model_name='masstransfervolume',
            name='series_instance_uid_pseudonymized',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
    ]
