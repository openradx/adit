from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mass_transfer", "0002_two_phase_task_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="masstransfervolume",
            name="export_cleaned",
            field=models.BooleanField(default=False),
        ),
    ]
