# Generated migration to add study_datetime field to BatchQueryResult model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('batch_query', '0032_switch_to_procrastinate'),
    ]

    operations = [
        migrations.AddField(
            model_name='batchqueryresult',
            name='study_datetime',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
