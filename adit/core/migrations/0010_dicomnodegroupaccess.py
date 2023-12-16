# Generated by Django 4.2.7 on 2023-12-10 21:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("core", "0009_remove_queuedtask_eta_priority_created_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="DicomNodeGroupAccess",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("source", models.BooleanField(default=False)),
                ("destination", models.BooleanField(default=False)),
                (
                    "dicom_node",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="accesses",
                        to="core.dicomnode"
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="auth.group"),
                ),
            ],
            options={
                "verbose_name_plural": "DICOM node group accesses",
            },
        ),
        migrations.AddConstraint(
            model_name="dicomnodegroupaccess",
            constraint=models.UniqueConstraint(
                fields=("dicom_node", "group"), name="unique_dicom_node_per_group"
            ),
        ),
    ]