from django.conf import settings
from django.contrib.sites.models import Site
from django.db import models


class SiteProfileManager(models.Manager["SiteProfile"]):
    def get_current(self) -> "SiteProfile":
        # We create SiteProfile on the fly as data migrations don't work properly in transactional
        # tests. The database is completely flushed after each transaction test case and the
        # migrated data is gone. Also `serialized_rollback` doesn't work correctly when using
        # fixtures like `page` of Playwright (see my issue below). By creating the object on the
        # fly we make sure that it exists. The downside is that it is not really available in
        # the templates as we access it with `request.site.profile`, but which is ok as in
        # templates when something is not available it falls back to the default empty string.
        # We still use a data migration for the Site model as we only use it in the templates.
        # TODO: A solution in the future could be the below pull request with cloning the database
        # in transactional tests and then we can use data migrations again.
        # https://github.com/pytest-dev/pytest-django/issues/1117
        # https://github.com/wemake-services/django-test-migrations/issues/438
        # https://code.djangoproject.com/ticket/25251
        # https://github.com/django/django/pull/14147
        site_profile, _ = self.get_or_create(
            site_id=settings.SITE_ID,
            defaults={
                "meta_keywords": settings.SITE_META_KEYWORDS,
                "meta_description": settings.SITE_META_DESCRIPTION,
                "project_url": settings.SITE_PROJECT_URL,
            },
        )
        return site_profile


class SiteProfile(models.Model):
    meta_keywords = models.TextField(blank=True)
    meta_description = models.TextField(blank=True)
    project_url = models.URLField(blank=True)
    announcement = models.TextField(blank=True)
    maintenance = models.BooleanField(default=False)
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name="profile")

    objects: SiteProfileManager = SiteProfileManager()

    def __str__(self):
        return f"Site profile for {self.site}"


class AppSettings(models.Model):
    id: int
    locked = models.BooleanField(default=False)

    class Meta:
        abstract = True

    @classmethod
    def get(cls):
        return cls.objects.first()
