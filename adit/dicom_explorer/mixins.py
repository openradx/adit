from adit.core.mixins import LockedMixin

from .models import DicomExplorerSettings


# TODO: Use in dicom explorer
class DicomExplorerLockedMixin(LockedMixin):
    settings_model = DicomExplorerSettings
