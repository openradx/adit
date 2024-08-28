from django.db import models

from adit.core.models import DicomAppSettings


class DicomExplorerSettings(DicomAppSettings):
    class Meta:
        verbose_name_plural = "DICOM explorer settings"


# A dummy model for permissions that depend on no real model
# Adapted from https://stackoverflow.com/a/37988537/166229
class PermissionSupport(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = (("query_dicom_server", "Query DICOM Server"),)

    def __str__(self) -> str:
        return f"{self.__class__.__name__} [{self.pk}]"
