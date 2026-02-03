from adit_radis_shared.common.mixins import LockedMixin

from .apps import SECTION_NAME
from .models import MassTransferSettings


class MassTransferLockedMixin(LockedMixin):
    settings_model = MassTransferSettings
    section_name = SECTION_NAME
