from django.db import migrations

from adit_radis_shared.common.utils.migration_utils import procrastinate_on_delete_sql


class Migration(migrations.Migration):

    dependencies = [
        ("mass_transfer", "0002_move_source_destination_to_task"),
    ]

    operations = [
        migrations.RunSQL(
            sql=procrastinate_on_delete_sql("mass_transfer", "masstransfertask"),
            reverse_sql=procrastinate_on_delete_sql(
                "mass_transfer", "masstransfertask", reverse=True
            ),
        ),
    ]
