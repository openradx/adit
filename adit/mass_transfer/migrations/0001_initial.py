from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

from adit_radis_shared.common.utils.migration_utils import procrastinate_on_delete_sql


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0015_delete_queuedtask"),
        ("procrastinate", "0028_add_cancel_states"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MassTransferFilter",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("modality", models.CharField(blank=True, default="", max_length=16)),
                ("institution_name", models.CharField(blank=True, default="", max_length=128)),
                ("apply_institution_on_study", models.BooleanField(default=True)),
                ("study_description", models.CharField(blank=True, default="", max_length=256)),
                ("series_description", models.CharField(blank=True, default="", max_length=256)),
                ("series_number", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mass_transfer_filters",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("name", "id"),
            },
        ),
        migrations.CreateModel(
            name="MassTransferSettings",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("locked", models.BooleanField(default=False)),
                ("suspended", models.BooleanField(default=False)),
            ],
            options={
                "verbose_name_plural": "Mass transfer settings",
            },
        ),
        migrations.CreateModel(
            name="MassTransferJob",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("UV", "Unverified"),
                            ("PE", "Pending"),
                            ("IP", "In Progress"),
                            ("CI", "Canceling"),
                            ("CA", "Canceled"),
                            ("SU", "Success"),
                            ("WA", "Warning"),
                            ("FA", "Failure"),
                        ],
                        default="UV",
                        max_length=2,
                    ),
                ),
                ("urgent", models.BooleanField(default=False)),
                ("message", models.TextField(blank=True, default="")),
                ("send_finished_mail", models.BooleanField(default=False)),
                ("convert_to_nifti", models.BooleanField(default=False)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("start", models.DateTimeField(blank=True, null=True)),
                ("end", models.DateTimeField(blank=True, null=True)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                (
                    "partition_granularity",
                    models.CharField(
                        choices=[("daily", "Daily"), ("weekly", "Weekly")],
                        default="daily",
                        max_length=16,
                    ),
                ),
                ("pseudonymize", models.BooleanField(default=True)),
                (
                    "destination",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="core.dicomnode",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mass_transfer_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="core.dicomnode",
                    ),
                ),
                (
                    "filters",
                    models.ManyToManyField(blank=True, related_name="jobs", to="mass_transfer.masstransferfilter"),
                ),
            ],
            options={
                "abstract": False,
                "permissions": [("can_process_urgently", "Can process urgently")],
            },
        ),
        migrations.CreateModel(
            name="MassTransferTask",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PE", "Pending"),
                            ("IP", "In Progress"),
                            ("CA", "Canceled"),
                            ("SU", "Success"),
                            ("WA", "Warning"),
                            ("FA", "Failure"),
                        ],
                        default="PE",
                        max_length=2,
                    ),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("message", models.TextField(blank=True, default="")),
                ("log", models.TextField(blank=True, default="")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("start", models.DateTimeField(blank=True, null=True)),
                ("end", models.DateTimeField(blank=True, null=True)),
                ("partition_start", models.DateTimeField()),
                ("partition_end", models.DateTimeField()),
                ("partition_key", models.CharField(max_length=64)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tasks",
                        to="mass_transfer.masstransferjob",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="core.dicomnode",
                    ),
                ),
                (
                    "queued_job",
                    models.OneToOneField(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="procrastinate.procrastinatejob",
                    ),
                ),
            ],
            options={
                "ordering": ("id",),
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="MassTransferVolume",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("exported", "Exported"),
                            ("converted", "Converted"),
                            ("error", "Error"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("partition_key", models.CharField(max_length=64)),
                ("pseudonym", models.CharField(blank=True, default="", max_length=64)),
                ("patient_id", models.CharField(blank=True, default="", max_length=64)),
                ("accession_number", models.CharField(blank=True, default="", max_length=64)),
                ("study_instance_uid", models.CharField(max_length=64)),
                ("series_instance_uid", models.CharField(max_length=64)),
                ("modality", models.CharField(blank=True, default="", max_length=16)),
                ("study_description", models.CharField(blank=True, default="", max_length=256)),
                ("series_description", models.CharField(blank=True, default="", max_length=256)),
                ("series_number", models.IntegerField(blank=True, null=True)),
                ("study_datetime", models.DateTimeField()),
                ("institution_name", models.CharField(blank=True, default="", max_length=128)),
                ("number_of_images", models.PositiveIntegerField(default=0)),
                ("exported_folder", models.TextField(blank=True, default="")),
                ("export_cleaned", models.BooleanField(default=False)),
                ("converted_file", models.TextField(blank=True, default="")),
                ("log", models.TextField(blank=True, default="")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="volumes",
                        to="mass_transfer.masstransferjob",
                    ),
                ),
            ],
            options={
                "ordering": ("study_datetime", "series_instance_uid"),
            },
        ),
        migrations.AddIndex(
            model_name="masstransferjob",
            index=models.Index(fields=["owner", "status"], name="mass_trans_owner_i_2403f1_idx"),
        ),
        migrations.AddConstraint(
            model_name="masstransferfilter",
            constraint=models.CheckConstraint(
                condition=~models.Q(name=""),
                name="mass_transfer_filter_name_not_blank",
            ),
        ),
        migrations.AddConstraint(
            model_name="masstransferfilter",
            constraint=models.UniqueConstraint(
                fields=("owner", "name"),
                name="mass_transfer_filter_unique_owner_name",
            ),
        ),
        migrations.AddConstraint(
            model_name="masstransfervolume",
            constraint=models.UniqueConstraint(
                fields=("job", "series_instance_uid"),
                name="mass_transfer_unique_series_per_job",
            ),
        ),
        migrations.RunSQL(
            sql=procrastinate_on_delete_sql("mass_transfer", "masstransfertask"),
            reverse_sql=procrastinate_on_delete_sql(
                "mass_transfer", "masstransfertask", reverse=True
            ),
        ),
    ]
