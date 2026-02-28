import django.db.models.deletion
from django.db import migrations, models


def migrate_pseudonymize_to_anonymization_mode(apps, schema_editor):
    MassTransferJob = apps.get_model("mass_transfer", "MassTransferJob")
    MassTransferJob.objects.filter(pseudonymize=True).update(anonymization_mode="pseudonymize")
    MassTransferJob.objects.filter(pseudonymize=False).update(anonymization_mode="none")


class Migration(migrations.Migration):
    dependencies = [
        ("mass_transfer", "0003_collapse_single_phase"),
    ]

    operations = [
        migrations.AddField(
            model_name="masstransferjob",
            name="anonymization_mode",
            field=models.CharField(
                choices=[
                    ("none", "No anonymization"),
                    ("pseudonymize", "Pseudonymize"),
                    ("pseudonymize_with_linking", "Pseudonymize with linking"),
                ],
                default="pseudonymize",
                max_length=32,
            ),
        ),
        migrations.RunPython(
            migrate_pseudonymize_to_anonymization_mode,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="masstransferjob",
            name="pseudonymize",
        ),
        migrations.CreateModel(
            name="MassTransferAssociation",
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
                ("pseudonym", models.CharField(max_length=64)),
                ("patient_id", models.CharField(max_length=64)),
                ("original_study_instance_uid", models.CharField(max_length=128)),
                ("pseudonymized_study_instance_uid", models.CharField(max_length=128)),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="associations",
                        to="mass_transfer.masstransferjob",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="associations",
                        to="mass_transfer.masstransfertask",
                    ),
                ),
            ],
            options={
                "ordering": ("id",),
            },
        ),
        migrations.AddConstraint(
            model_name="masstransferassociation",
            constraint=models.UniqueConstraint(
                fields=("job", "original_study_instance_uid"),
                name="mass_transfer_unique_association_per_study",
            ),
        ),
    ]
