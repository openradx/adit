from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import send_mail


class Command(BaseCommand):
    help = "Send a test mail using the provided Email settings."

    def handle(self, *args, **options):
        send_mail(
            "Test Mail",
            "This is a test mail sent by ADIT.",
            settings.ADMINS[0][1],
            ["kai.schlamp@gmail.com"],
            fail_silently=False,
        )
