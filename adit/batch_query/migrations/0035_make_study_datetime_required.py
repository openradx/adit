# Generated migration to make study_datetime non-nullable

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('batch_query', '0034_populate_study_datetime'),
    ]

    operations = [
        migrations.AlterField(
            model_name='batchqueryresult',
            name='study_datetime',
            field=models.DateTimeField(),
        ),
    ]
