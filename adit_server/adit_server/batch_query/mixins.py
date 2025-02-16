from adit_radis_shared.common.mixins import LockedMixin

from .apps import SECTION_NAME
from .models import BatchQuerySettings


class BatchQueryLockedMixin(LockedMixin):
    settings_model = BatchQuerySettings
    section_name = SECTION_NAME
