# Created manually, see https://stackoverflow.com/a/49108587/166229

from django.db import migrations
from django.conf import settings


def update_site_name(apps, _):
    SiteModel = apps.get_model("sites", "Site")

    SiteModel.objects.update_or_create(
        pk=settings.SITE_ID,
        defaults={
            "domain": settings.SITE_DOMAIN,
            "name": settings.SITE_NAME,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        # No need anymore for this data migration as we to it in common,
        # see common/migrations/0002_update_or_create_site.py
        # migrations.RunPython(update_site_name),
    ]
