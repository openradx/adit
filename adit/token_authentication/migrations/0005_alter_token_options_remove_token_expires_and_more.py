# Generated by Django 4.2.3 on 2023-07-23 23:16

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("token_authentication", "0004_rename_token_string_token_token_hashed"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="token",
            options={
                "permissions": [
                    ("can_generate_never_expiring_token", "Can generate never expiring token")
                ]
            },
        ),
        migrations.RemoveField(
            model_name="token",
            name="expires",
        ),
        migrations.AlterField(
            model_name="token",
            name="expiry_time",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
