from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0017_review_fixes"),
    ]

    operations = [
        migrations.AddField(
            model_name="dicomserver",
            name="image_level_find_support",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Whether the server answers IMAGE-level queries completely. Turn it off for a "
                    "PACS that doesn't support them, caps their results or is slow at them."
                ),
            ),
        ),
    ]
