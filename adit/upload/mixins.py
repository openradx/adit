from adit.core.mixins import LockedMixin

from .apps import SECTION_NAME
from .models import UploadSettings


class UploadLockedMixin(LockedMixin):
    settings_model = UploadSettings
    section_name = SECTION_NAME
