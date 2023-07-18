import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from ...utils.vespa_utils import app_package


class Command(BaseCommand):
    help = "Setup the Vespa schema for the RADIS app"

    def handle(self, *args, **options):
        vespa_dir = Path("/tmp/radis_vespa")
        vespa_dir.mkdir(exist_ok=True)
        app_package.to_files(vespa_dir)

        vespa_host = settings.VESPA_HOST
        vespa_config_port = settings.VESPA_CONFIG_PORT
        vespa_url = f"http://{vespa_host}:{vespa_config_port}/"
        cmd = f"vespa deploy --wait 300 -t {vespa_url} {vespa_dir.as_posix()}"
        print(f"Running: {cmd}")
        subprocess.run(cmd, shell=True, check=True)
        print("RADIS Vespa app deployed successfully!")
