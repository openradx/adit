from django.contrib.sites.models import Site
from django.db import models


class SiteProfile(models.Model):
    meta_keywords = models.TextField(blank=True)
    meta_description = models.TextField(blank=True)
    project_url = models.URLField(blank=True)
    announcement = models.TextField(blank=True)
    maintenance = models.BooleanField(default=False)
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name="profile")

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
