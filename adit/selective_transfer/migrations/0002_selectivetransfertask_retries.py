# Generated by Django 3.1.3 on 2021-01-26 17:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('selective_transfer', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='selectivetransfertask',
            name='retries',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
