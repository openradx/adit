# Generated by Django 4.0.6 on 2022-08-11 18:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qido_rs', '0003_remove_dicomqidoresult_accession_number_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dicomqidoresult',
            name='query_results',
            field=models.JSONField(default=list),
        ),
    ]
