from typing import Literal

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class SendTestMailCommand(BaseCommand):
    project_name: Literal["ADIT", "RADIS"]
    help = "Send a test mail using the provided Email settings."

    def add_arguments(self, parser):
        parser.add_argument("to_address", nargs="?", type=str, default=settings.ADMINS[0][1])

    def handle(self, *args, **options):
        to_address = options["to_address"]

        send_mail(
            f"[{self.project_name}] Test Mail",
            f"This is a test mail sent by {self.project_name}.",
            settings.SERVER_EMAIL,
            [to_address],
            fail_silently=False,
        )
