from adit_radis_shared.common.mixins import LockedMixin

from .apps import SECTION_NAME
from .models import SelectiveTransferSettings


class SelectiveTransferLockedMixin(LockedMixin):
    settings_model = SelectiveTransferSettings
    section_name = SECTION_NAME
