import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ...vespa_app import VespaConfigurator, vespa_app


class Command(BaseCommand):
    help = "Generate and/or deploy the Vespa application package."

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
            "--generate",
            action="store_true",
            help=(
                "Generate the XML application package deployment files. Can be used together "
                "with --deploy to deploy those files to a Vespa config server."
            ),
        )
        parser.add_argument(
            "--deploy",
            action="store_true",
            help=(
                "Deploy the Vespa application with previously generated XML application "
                "files to a Vespa config server. Can be used together with --generate option to "
                "create those files."
            ),
        )
        parser.add_argument(
            "--folder",
            default=None,
            help=(
                "A folder for the XML application package deployment files. It is optional when "
                "using both --generate and --deploy option together as a temporary folder is then "
                "generated on the fly and deleted after deployment. Otherwise this folder is used "
                "for the generated files or as the folder the application is deployed from."
            ),
        )

    def handle(self, *args, **options):
        if not options["generate"] and not options["deploy"]:
            raise CommandError("Missing --generate or --deploy option.")

        if not options["folder"] and (
            options["generate"]
            and not options["deploy"]
            or not options["generate"]
            and options["deploy"]
        ):
            raise CommandError(
                "A folder must be provided when only one of the "
                "--generate or --deploy options are used."
            )

        app_folder: Path | None = None
        if options["folder"]:
            app_folder = Path(options["folder"])

        tmp_dir: tempfile.TemporaryDirectory | None = None

        if options["generate"]:
            if app_folder:
                app_folder.mkdir(parents=True, exist_ok=True)
            else:
                tmp_dir = tempfile.TemporaryDirectory(prefix="radis_")
                app_folder = Path(tmp_dir.name)

            print(f"Generating deployment files in {app_folder.absolute()}")
            vespa_app.get_app_package().to_files(app_folder)

            configurator = VespaConfigurator(app_folder)
            configurator.apply()

        if options["deploy"]:
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

            if not app_folder:
                raise AssertionError("Missing app folder. Should be present by now.")

            cmd = f"vespa deploy --wait 300 -t {vespa_url} {app_folder.absolute()}"

            print(f"Running: {cmd}")
            subprocess.run(cmd, shell=True, check=True)

        if tmp_dir:
            tmp_dir.cleanup()
