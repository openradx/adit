# Generated by Django 4.2.2 on 2023-06-25 10:57

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("batch_transfer", "0013_convert_json_to_text"),
    ]

    operations = [
        migrations.AlterField(
            model_name="batchtransfertask",
            name="lines",
            field=models.TextField(
                validators=[
                    django.core.validators.RegexValidator(
                        message="Enter only digits separated by commas.",
                        regex="^\\s*\\d+(?:\\s*,\\s*\\d+)*\\s*\\Z",
                    )
                ]
            ),
        ),
    ]
