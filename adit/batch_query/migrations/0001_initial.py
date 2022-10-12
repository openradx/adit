# Generated by Django 4.1.1 on 2022-09-30 13:08

import adit.core.validators
import datetime
from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BatchQueryJob",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
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
                ("created", models.DateTimeField(auto_now_add=True)),
                ("start", models.DateTimeField(blank=True, null=True)),
                ("end", models.DateTimeField(blank=True, null=True)),
                ("project_name", models.CharField(max_length=150)),
                ("project_description", models.TextField(max_length=2000)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_jobs",
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
            ],
            options={
                "permissions": [("can_process_urgently", "Can process urgently")],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="BatchQuerySettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("locked", models.BooleanField(default=False)),
                ("suspended", models.BooleanField(default=False)),
                (
                    "slot_begin_time",
                    models.TimeField(
                        default=datetime.time(22, 0),
                        help_text="Must be set in UTC time zone.",
                    ),
                ),
                (
                    "slot_end_time",
                    models.TimeField(
                        default=datetime.time(8, 0),
                        help_text="Must be set in UTC time zone.",
                    ),
                ),
                ("transfer_timeout", models.IntegerField(default=3)),
            ],
            options={
                "verbose_name_plural": "Batch query settings",
            },
        ),
        migrations.CreateModel(
            name="BatchQueryTask",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("task_id", models.PositiveIntegerField()),
                ("celery_task_id", models.CharField(max_length=255)),
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
                ("retries", models.PositiveSmallIntegerField(default=0)),
                ("message", models.TextField(blank=True, default="")),
                ("log", models.TextField(blank=True, default="")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("start", models.DateTimeField(blank=True, null=True)),
                ("end", models.DateTimeField(blank=True, null=True)),
                ("lines", models.JSONField(default=list)),
                (
                    "patient_id",
                    models.CharField(
                        blank=True,
                        max_length=64,
                        validators=[
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid backslash character",
                                regex="\\\\",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid control characters.",
                                regex="[\\f\\n\\r]",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid wildcard characters.",
                                regex="[\\*\\?]",
                            ),
                        ],
                    ),
                ),
                (
                    "patient_name",
                    models.CharField(
                        blank=True,
                        max_length=324,
                        validators=[
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid backslash character",
                                regex="\\\\",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid control characters.",
                                regex="[\\f\\n\\r]",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid wildcard characters.",
                                regex="[\\*\\?]",
                            ),
                        ],
                    ),
                ),
                (
                    "patient_birth_date",
                    models.DateField(
                        blank=True,
                        error_messages={"invalid": "Invalid date format."},
                        null=True,
                    ),
                ),
                (
                    "accession_number",
                    models.CharField(
                        blank=True,
                        max_length=32,
                        validators=[
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid backslash character",
                                regex="\\\\",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid control characters.",
                                regex="[\\f\\n\\r]",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid wildcard characters.",
                                regex="[\\*\\?]",
                            ),
                        ],
                    ),
                ),
                (
                    "study_date_start",
                    models.DateField(
                        blank=True,
                        error_messages={"invalid": "Invalid date format."},
                        null=True,
                    ),
                ),
                (
                    "study_date_end",
                    models.DateField(
                        blank=True,
                        error_messages={"invalid": "Invalid date format."},
                        null=True,
                    ),
                ),
                (
                    "modalities",
                    models.JSONField(
                        blank=True,
                        null=True,
                        validators=[adit.core.validators.validate_modalities],
                    ),
                ),
                (
                    "pseudonym",
                    models.CharField(
                        blank=True,
                        max_length=64,
                        validators=[
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid backslash character",
                                regex="\\\\",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid control characters.",
                                regex="[\\f\\n\\r]",
                            ),
                        ],
                    ),
                ),
                ("series_description", models.CharField(blank=True, max_length=64)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tasks",
                        to="batch_query.batchqueryjob",
                    ),
                ),
            ],
            options={
                "ordering": ("task_id",),
                "abstract": False,
                "unique_together": {("job", "task_id")},
            },
        ),
        migrations.CreateModel(
            name="BatchQueryResult",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "patient_id",
                    models.CharField(
                        max_length=64,
                        validators=[
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid backslash character",
                                regex="\\\\",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid control characters.",
                                regex="[\\f\\n\\r]",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid wildcard characters.",
                                regex="[\\*\\?]",
                            ),
                        ],
                    ),
                ),
                (
                    "patient_name",
                    models.CharField(
                        max_length=324,
                        validators=[
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid backslash character",
                                regex="\\\\",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid control characters.",
                                regex="[\\f\\n\\r]",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid wildcard characters.",
                                regex="[\\*\\?]",
                            ),
                        ],
                    ),
                ),
                ("patient_birth_date", models.DateField()),
                (
                    "study_uid",
                    models.CharField(
                        max_length=64,
                        validators=[
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid backslash character",
                                regex="\\\\",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid control characters.",
                                regex="[\\f\\n\\r]",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid wildcard characters.",
                                regex="[\\*\\?]",
                            ),
                        ],
                    ),
                ),
                (
                    "accession_number",
                    models.CharField(
                        max_length=32,
                        validators=[
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid backslash character",
                                regex="\\\\",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid control characters.",
                                regex="[\\f\\n\\r]",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid wildcard characters.",
                                regex="[\\*\\?]",
                            ),
                        ],
                    ),
                ),
                ("study_date", models.DateField()),
                ("study_time", models.TimeField()),
                (
                    "study_description",
                    models.CharField(
                        max_length=64,
                        validators=[
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid backslash character",
                                regex="\\\\",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid control characters.",
                                regex="[\\f\\n\\r]",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid wildcard characters.",
                                regex="[\\*\\?]",
                            ),
                        ],
                    ),
                ),
                (
                    "modalities",
                    models.JSONField(
                        blank=True,
                        null=True,
                        validators=[adit.core.validators.validate_modalities],
                    ),
                ),
                ("image_count", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "pseudonym",
                    models.CharField(
                        blank=True,
                        max_length=64,
                        validators=[
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid backslash character",
                                regex="\\\\",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid control characters.",
                                regex="[\\f\\n\\r]",
                            ),
                        ],
                    ),
                ),
                (
                    "series_uid",
                    models.CharField(
                        blank=True,
                        max_length=64,
                        validators=[
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid backslash character",
                                regex="\\\\",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid control characters.",
                                regex="[\\f\\n\\r]",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid wildcard characters.",
                                regex="[\\*\\?]",
                            ),
                        ],
                    ),
                ),
                (
                    "series_description",
                    models.CharField(
                        blank=True,
                        max_length=64,
                        validators=[
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid backslash character",
                                regex="\\\\",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid control characters.",
                                regex="[\\f\\n\\r]",
                            ),
                            django.core.validators.RegexValidator(
                                inverse_match=True,
                                message="Contains invalid wildcard characters.",
                                regex="[\\*\\?]",
                            ),
                        ],
                    ),
                ),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="batch_query.batchqueryjob",
                    ),
                ),
                (
                    "query",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="batch_query.batchquerytask",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="batchqueryjob",
            index=models.Index(
                fields=["owner", "status"], name="batch_query_owner_i_265d08_idx"
            ),
        ),
    ]
