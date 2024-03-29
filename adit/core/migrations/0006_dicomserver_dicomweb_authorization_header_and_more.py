# Generated by Django 4.2.2 on 2023-06-29 12:52

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_auto_20210510_1645"),
    ]

    operations = [
        migrations.AddField(
            model_name="dicomserver",
            name="dicomweb_authorization_header",
            field=models.CharField(blank=True, max_length=2000),
        ),
        migrations.AddField(
            model_name="dicomserver",
            name="dicomweb_qido_prefix",
            field=models.CharField(blank=True, max_length=2000),
        ),
        migrations.AddField(
            model_name="dicomserver",
            name="dicomweb_stow_prefix",
            field=models.CharField(blank=True, max_length=2000),
        ),
        migrations.AddField(
            model_name="dicomserver",
            name="dicomweb_wado_prefix",
            field=models.CharField(blank=True, max_length=2000),
        ),
    ]
