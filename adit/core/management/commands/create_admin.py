import os
from django.core.management.base import BaseCommand
from adit.accounts.models import User  # pylint: disable=import-error


class Command(BaseCommand):
    help = "Creates a superuser admin account from environment variables."

    def handle(self, *args, **options):
        try:
            username = os.environ["ADMIN_USERNAME"]
            first_name = os.environ["ADMIN_FIRST_NAME"]
            last_name = os.environ["ADMIN_LAST_NAME"]
            email = os.environ["ADMIN_EMAIL"]
            password = os.environ["ADMIN_PASSWORD"]

            try:
                User.objects.get(username=username)
                print(f"Admin user {username} already exists. Skipping admin creation.")
            except User.DoesNotExist:
                User.objects.create_superuser(
                    username,
                    email,
                    password,
                    first_name=first_name,
                    last_name=last_name,
                )
                print(f"Created admin user {username}.")

        except KeyError as err:
            print("Missing environment variable for creating admin user: " + err)