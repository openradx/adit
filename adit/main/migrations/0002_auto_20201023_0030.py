# Generated by Django 3.1.2 on 2020-10-22 22:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='dicomfolder',
            name='quota',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='dicomfolder',
            name='warn_size',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]