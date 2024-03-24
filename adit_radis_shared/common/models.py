from django.db import models


class ProjectSettings(models.Model):
    id: int
    maintenance_mode = models.BooleanField(default=False)
    announcement = models.TextField(blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.__class__.__name__} [ID {self.id}]"

    @classmethod
    def get(cls):
        return cls.objects.first()


class AppSettings(models.Model):
    id: int
    locked = models.BooleanField(default=False)

    class Meta:
        abstract = True

    @classmethod
    def get(cls):
        return cls.objects.first()
