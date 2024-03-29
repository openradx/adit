# Generated by Django 4.2.5 on 2023-10-23 11:04

import django.contrib.postgres.fields
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("batch_query", "0024_merge_20231019_0724"),
    ]

    operations = [
        migrations.AddField(
            model_name="batchqueryresult",
            name="modalities_new",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(
                    max_length=16,
                    validators=[
                        django.core.validators.RegexValidator(
                            "^[a-zA-Z]*$", "Only letters A-Z are allowed."
                        )
                    ],
                ),
                default=[],
                size=None,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="batchquerytask",
            name="lines_new",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.PositiveSmallIntegerField(), default=[], size=None
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="batchquerytask",
            name="modalities_new",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(
                    max_length=16,
                    validators=[
                        django.core.validators.RegexValidator(
                            "^[a-zA-Z]*$", "Only letters A-Z are allowed."
                        )
                    ],
                ),
                default=[],
                size=None,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="batchquerytask",
            name="series_numbers_new",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(
                    max_length=12,
                    validators=[
                        django.core.validators.RegexValidator(
                            "^\\s*[-+]?[0-9]+\\s*$", "Invalid string representation of a number."
                        )
                    ],
                ),
                default=[],
                size=None,
            ),
            preserve_default=False,
        ),
    ]
