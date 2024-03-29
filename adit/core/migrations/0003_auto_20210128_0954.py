# Generated by Django 3.1.3 on 2021-01-28 09:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_UPDATE_SITE_NAME'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dicomfolder',
            name='quota',
            field=models.PositiveIntegerField(blank=True, help_text='The disk quota of this folder in GB.', null=True),
        ),
        migrations.AlterField(
            model_name='dicomfolder',
            name='warn_size',
            field=models.PositiveIntegerField(blank=True, help_text='When to warn the admins by Email (used space in GB).', null=True),
        ),
    ]
