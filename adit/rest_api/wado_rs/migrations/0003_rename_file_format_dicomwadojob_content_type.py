# Generated by Django 4.0.6 on 2022-08-16 13:32

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wado_rs', '0002_dicomwadojob_boundary'),
    ]

    operations = [
        migrations.RenameField(
            model_name='dicomwadojob',
            old_name='file_format',
            new_name='content_type',
        ),
    ]
