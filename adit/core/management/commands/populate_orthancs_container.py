from typing import Annotated

from adit_radis_shared.maintenance_commands.management.base.maintenance_command import (
    MaintenanceCommand,
)
from typer import Option


class Command(MaintenanceCommand):
    """Start stack with docker compose"""

    def handle(
        self,
        reset: Annotated[bool, Option(help="Do not build images")] = False,
        simulate: Annotated[bool, Option(help="Simulate the command")] = False,
    ):
        """Populate Orthancs with example DICOMs"""
        cmd = f"{self.build_compose_cmd()} exec web python manage.py populate_orthancs"
        if reset:
            cmd += " --reset"

        self.execute_cmd(cmd, simulate=simulate)
