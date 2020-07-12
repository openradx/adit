import glob
import re
import os
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Reset all migrations to only have one initial migration per app (dangerous!).'

    def handle(self, *args, **options):
        base_dir = settings.BASE_DIR

        migration_paths = glob.glob(f'{base_dir}/*/migrations/**/*.py', recursive=True)
        regex = re.compile(r'.*/__init__\.py$')
        migration_paths = [i for i in migration_paths if not regex.match(i)]
        for migration_path in migration_paths:
            os.remove(migration_path)

        pyc_paths = glob.glob(f'{base_dir}/*/migrations/**/*.pyc', recursive=True)
        for pyc_path in pyc_paths:
            os.remove(pyc_path)

        call_command('reset_db', '--noinput') # needs django_extensions installed
        call_command('makemigrations')
        call_command('migrate')