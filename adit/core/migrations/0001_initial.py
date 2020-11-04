# Generated by Django 3.1.3 on 2020-11-04 21:40

import adit.core.validators
from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
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
                ('active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='TransferJob',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_type', models.CharField(choices=[('ST', 'Selective Transfer'), ('BT', 'Batch Transfer'), ('CT', 'Continuous Transfer')], max_length=2)),
                ('status', models.CharField(choices=[('UV', 'Unverified'), ('PE', 'Pending'), ('IP', 'In Progress'), ('CI', 'Canceling'), ('CA', 'Canceled'), ('SU', 'Success'), ('WA', 'Warning'), ('FA', 'Failure')], default='UV', max_length=2)),
                ('message', models.TextField(blank=True, default='')),
                ('trial_protocol_id', models.CharField(blank=True, max_length=64)),
                ('trial_protocol_name', models.CharField(blank=True, max_length=64)),
                ('archive_password', models.CharField(blank=True, max_length=50)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('start', models.DateTimeField(blank=True, null=True)),
                ('end', models.DateTimeField(blank=True, null=True)),
                ('destination', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.dicomnode')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transfer_jobs', to=settings.AUTH_USER_MODEL)),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.dicomnode')),
            ],
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
                ('patient_root_find_support', models.BooleanField(default=True)),
                ('patient_root_get_support', models.BooleanField(default=True)),
                ('patient_root_move_support', models.BooleanField(default=True)),
                ('study_root_find_support', models.BooleanField(default=True)),
                ('study_root_get_support', models.BooleanField(default=True)),
                ('study_root_move_support', models.BooleanField(default=True)),
            ],
            bases=('core.dicomnode',),
        ),
        migrations.CreateModel(
            name='TransferTask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField(blank=True, null=True)),
                ('patient_id', models.CharField(max_length=64)),
                ('study_uid', models.CharField(max_length=64)),
                ('series_uids', models.JSONField(blank=True, null=True)),
                ('pseudonym', models.CharField(blank=True, max_length=64, validators=[adit.core.validators.validate_pseudonym])),
                ('status', models.CharField(choices=[('PE', 'Pending'), ('IP', 'In Progress'), ('CA', 'Canceled'), ('SU', 'Success'), ('FA', 'Failure')], default='PE', max_length=2)),
                ('message', models.TextField(blank=True, default='')),
                ('log', models.TextField(blank=True, default='')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('start', models.DateTimeField(blank=True, null=True)),
                ('end', models.DateTimeField(blank=True, null=True)),
                ('content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='contenttypes.contenttype')),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='core.transferjob')),
            ],
            options={
                'ordering': ('id',),
            },
        ),
        migrations.AddIndex(
            model_name='transferjob',
            index=models.Index(fields=['owner', 'status'], name='core_transf_owner_i_fb3433_idx'),
        ),
    ]