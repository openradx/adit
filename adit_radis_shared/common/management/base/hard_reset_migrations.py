from typing import Literal

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class HardResetMigrationsCommand(BaseCommand):
    project: Literal["adit", "radis"]
    help = "Reset all migration files (dangerous!!!)."

    def handle(self, *args, **options):
        migration_paths = settings.BASE_DIR.glob(f"./{self.project}/*/migrations/**/*.py")
        migration_paths = [i for i in migration_paths if i.name != "__init__.py"]
        for migration_path in migration_paths:
            migration_path.unlink()

        pyc_paths = settings.BASE_DIR.glob("*/migrations/**/*.pyc")
        for pyc_path in pyc_paths:
            pyc_path.unlink()

        call_command("reset_db", "--noinput")  # needs django_extensions installed
        call_command("makemigrations")
        call_command("migrate")
