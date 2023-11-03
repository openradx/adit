# Generated by Django 3.1.3 on 2021-01-28 16:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('batch_transfer', '0002_batchtransfertask_retries'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='batchtransfertask',
            options={'ordering': ('task_id',)},
        ),
        migrations.RenameField(
            model_name='batchtransfertask',
            old_name='batch_id',
            new_name='task_id',
        ),
        migrations.AlterUniqueTogether(
            name='batchtransfertask',
            unique_together={('job', 'task_id')},
        ),
    ]