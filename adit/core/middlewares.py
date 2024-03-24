from adit_radis_shared.common.middlewares import BaseMaintenanceMiddleware

from .models import CoreSettings


class MaintenanceMiddleware(BaseMaintenanceMiddleware):
    project_settings = CoreSettings
    template_name = "core/maintenance.html"
