# Generated migration to remove old study_date and study_time fields

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('batch_query', '0035_make_study_datetime_required'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='batchqueryresult',
            name='study_date',
        ),
        migrations.RemoveField(
            model_name='batchqueryresult',
            name='study_time',
        ),
    ]
