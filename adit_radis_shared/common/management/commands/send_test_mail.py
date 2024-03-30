from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Send a test mail using the provided Email settings."

    def add_arguments(self, parser):
        parser.add_argument("to_address", nargs="?", type=str, default=settings.ADMINS[0][1])

    def handle(self, *args, **options):
        to_address = options["to_address"]
        site = Site.objects.get_current()

        send_mail(
            f"[{site.name}] Test Mail",
            f"This is a test mail sent by {site.name}.",
            settings.SERVER_EMAIL,
            [to_address],
            fail_silently=False,
        )
