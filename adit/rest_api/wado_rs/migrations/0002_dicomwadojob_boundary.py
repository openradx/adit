# Generated by Django 4.0.6 on 2022-08-07 14:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wado_rs', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='dicomwadojob',
            name='boundary',
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
