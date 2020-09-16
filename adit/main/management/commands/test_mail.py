from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import send_mail


class Command(BaseCommand):
    help = "Send a test mail using the provided Email settings."

    def add_arguments(self, parser):
        parser.add_argument("to_address", type=str)

    def handle(self, *args, **options):
        to_address = options["to_address"]

        send_mail(
            "Test Mail",
            "This is a test mail sent by ADIT.",
            settings.ADMINS[0][1],
            [to_address],
            fail_silently=False,
        )
