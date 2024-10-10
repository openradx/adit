from adit.core.models import DicomAppSettings


class UploadSettings(DicomAppSettings):
    class Meta:
        verbose_name_plural = "Upload settings"
        default_permissions = ()
        permissions = [
            ("can_upload_data", "Can upload data"),
        ]


