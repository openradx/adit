from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0018_dicomserver_image_level_find_support"),
    ]

    operations = [
        migrations.AddField(
            model_name="dicomserver",
            name="accepted_calling_ae_titles",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "AE titles, separated by commas, that the server sends the images of a "
                    "C-MOVE from. Images from other AE titles are ignored then. Empty accepts "
                    "any AE title, as some PACS send from another AE title than they are "
                    "queried with."
                ),
                max_length=1000,
            ),
        ),
    ]
