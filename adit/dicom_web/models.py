from adit.core.models import DicomAppSettings


class DicomWebSettings(DicomAppSettings):
    class Meta:
        verbose_name_plural = "Dicom Web settings"
        permissions = [
            ("can_query", "Can query"),
            ("can_retrieve", "Can retrieve"),
            ("can_store", "Can store"),
        ]
