# Generated by Django 4.2.5 on 2023-10-24 12:34

import django.contrib.postgres.fields
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("batch_query", "0028_rename_modalities_new_batchqueryresult_modalities_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="batchquerytask",
            name="modalities",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(
                    max_length=16,
                    validators=[
                        django.core.validators.RegexValidator(
                            "^[a-zA-Z]*$", "Only letters A-Z are allowed."
                        )
                    ],
                ),
                blank=True,
                default=list,
                size=None,
            ),
        ),
        migrations.AlterField(
            model_name="batchquerytask",
            name="series_numbers",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(
                    max_length=12,
                    validators=[
                        django.core.validators.RegexValidator(
                            "^\\s*[-+]?[0-9]+\\s*$", "Invalid string representation of a number."
                        )
                    ],
                ),
                blank=True,
                default=list,
                size=None,
            ),
        ),
    ]