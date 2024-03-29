# Generated by Django 4.2.3 on 2023-07-27 14:48

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("token_authentication", "0009_rename_author_token_owner_alter_token_client_and_more"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="token",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="token",
            constraint=models.UniqueConstraint(
                fields=("client", "owner"), name="unique_client_per_user"
            ),
        ),
    ]
