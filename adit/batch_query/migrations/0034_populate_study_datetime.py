# Generated migration to populate study_datetime field

from django.db import migrations
from datetime import datetime


def populate_study_datetime(apps, schema_editor):
    """
    Populate the study_datetime field by combining study_date and study_time.
    """
    BatchQueryResult = apps.get_model('batch_query', 'BatchQueryResult')
    
    for result in BatchQueryResult.objects.all():
        if result.study_date and result.study_time:
            # Combine date and time into datetime
            result.study_datetime = datetime.combine(result.study_date, result.study_time)
            result.save(update_fields=['study_datetime'])


def reverse_populate_study_datetime(apps, schema_editor):
    """
    Reverse migration: clear the study_datetime field.
    """
    BatchQueryResult = apps.get_model('batch_query', 'BatchQueryResult')
    BatchQueryResult.objects.update(study_datetime=None)


class Migration(migrations.Migration):

    dependencies = [
        ('batch_query', '0033_add_batchqueryjob_study_datetime'),
    ]

    operations = [
        migrations.RunPython(
            populate_study_datetime,
            reverse_populate_study_datetime,
        ),
    ]
