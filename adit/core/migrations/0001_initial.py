# Generated by Django 3.1.3 on 2021-01-13 11:06

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CoreSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('maintenance_mode', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name_plural': 'Core settings',
            },
        ),
        migrations.CreateModel(
            name='DicomNode',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('node_type', models.CharField(choices=[('SV', 'Server'), ('FO', 'Folder')], max_length=2)),
                ('name', models.CharField(max_length=64, unique=True)),
                ('source_active', models.BooleanField(default=True)),
                ('destination_active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='DicomFolder',
            fields=[
                ('dicomnode_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.dicomnode')),
                ('path', models.CharField(max_length=256)),
                ('quota', models.PositiveIntegerField(blank=True, help_text='The disk quota of this folder in MB.', null=True)),
                ('warn_size', models.PositiveIntegerField(blank=True, help_text='When to warn the admins by Email (used space in MB).', null=True)),
            ],
            bases=('core.dicomnode',),
        ),
        migrations.CreateModel(
            name='DicomServer',
            fields=[
                ('dicomnode_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.dicomnode')),
                ('ae_title', models.CharField(max_length=16, unique=True)),
                ('host', models.CharField(max_length=255)),
                ('port', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(65535)])),
                ('patient_root_find_support', models.BooleanField(default=False)),
                ('patient_root_get_support', models.BooleanField(default=False)),
                ('patient_root_move_support', models.BooleanField(default=False)),
                ('study_root_find_support', models.BooleanField(default=False)),
                ('study_root_get_support', models.BooleanField(default=False)),
                ('study_root_move_support', models.BooleanField(default=False)),
                ('store_scp_support', models.BooleanField(default=False)),
                ('dicomweb_root_url', models.CharField(max_length=2000)),
                ('dicomweb_qido_support', models.BooleanField(default=False)),
                ('dicomweb_wado_support', models.BooleanField(default=False)),
                ('dicomweb_stow_support', models.BooleanField(default=False)),
            ],
            bases=('core.dicomnode',),
        ),
    ]
