from adit.core.mixins import LockedMixin

from .apps import SECTION_NAME
from .models import BatchTransferSettings


class BatchTransferLockedMixin(LockedMixin):
    settings_model = BatchTransferSettings
    section_name = SECTION_NAME
