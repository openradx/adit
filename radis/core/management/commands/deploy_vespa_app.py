import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from radis.core.vespa_app import vespa_app


class Command(BaseCommand):
    help = "Setup the Vespa schema for the RADIS app"

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default=None,
            help="Host of the Vespa config server (overwrites VESPA_HOST setting).",
        )
        parser.add_argument(
            "--port",
            default=None,
            type=int,
            help="Port of the Vespa config server (overwrites VESPA_CONFIG_PORT setting).",
        )
        parser.add_argument(
            "--folder",
            default=None,
            help=(
                "Explicit app package folder for deployment files, which is not deleted after "
                "deployment. Otherwise a temporary folder is used which gets cleaned up."
            ),
        )

    def handle(self, *args, **options):
        app_folder: Path
        tmp_dir: tempfile.TemporaryDirectory | None = None
        if options["folder"]:
            app_folder = Path(options["folder"])
            app_folder.mkdir(parents=True, exist_ok=True)
        else:
            tmp_dir = tempfile.TemporaryDirectory(prefix="radis_")
            app_folder = Path(tmp_dir.name)

        vespa_app.get_app_package().to_files(app_folder)

        vespa_host: str
        if options["host"]:
            vespa_host = options["host"]
        else:
            vespa_host = settings.VESPA_HOST

        vespa_config_port: int
        if options["port"]:
            vespa_config_port = options["port"]
        else:
            vespa_config_port = settings.VESPA_CONFIG_PORT

        vespa_url = f"http://{vespa_host}:{vespa_config_port}/"

        cmd = f"vespa deploy --wait 300 -t {vespa_url} {app_folder.as_posix()}"
        print(f"Running: {cmd}")
        subprocess.run(cmd, shell=True, check=True)

        if tmp_dir:
            tmp_dir.cleanup()

        print("RADIS Vespa app deployed successfully!")
