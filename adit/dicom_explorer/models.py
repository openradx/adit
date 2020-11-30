from django.db import models


# A dummy model for permissions that depend on no real model
# Adapted from https://stackoverflow.com/a/37988537/166229
class PermissionSupport(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = (("query_dicom_server", "Query DICOM Server"),)
