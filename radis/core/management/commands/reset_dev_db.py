from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Resets the development database. Clears it and populates it with (partly) fake data."

    def handle(self, *args, **options):
        call_command("reset_db", "--noinput")  # needs django_extensions installed
        call_command("migrate")
        call_command("populate_dev_db")
