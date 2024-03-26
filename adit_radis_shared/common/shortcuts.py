from django.conf import settings

from adit_radis_shared.common.models import SiteProfile


def get_site_profile() -> SiteProfile:
    site_profile = SiteProfile.objects.filter(site_id=settings.SITE_ID).first()
    assert site_profile
    return site_profile
