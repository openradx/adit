from os import environ

import factory
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandParser
from faker import Faker

from radis.accounts.factories import AdminUserFactory, UserFactory
from radis.accounts.models import User
from radis.core.factories import (
    ReportCollectionFactory,
    SavedReportFactory,
)

USER_COUNT = 3
REPORT_COLLECTIONS_COUNT = 5
REPORTS_PER_COLLECTION_COUNT = 3

fake = Faker()


def create_users():
    admin_data = {
        "username": environ.get("ADMIN_USERNAME"),
        "first_name": environ.get("ADMIN_FIRST_NAME"),
        "last_name": environ.get("ADMIN_LAST_NAME"),
        "email": environ.get("ADMIN_EMAIL"),
        "password": environ.get("ADMIN_PASSWORD"),
    }
    admin_data = {k: v for k, v in admin_data.items() if v is not None}
    admin = AdminUserFactory.create(**admin_data)

    users = [admin]

    for i in range(USER_COUNT):
        user = UserFactory.create()
        users.append(user)

    return users


def create_report_collections(users):
    for _ in range(REPORT_COLLECTIONS_COUNT):
        collection = ReportCollectionFactory.create(
            owner=factory.Faker("random_element", elements=users)
        )

        for _ in range(REPORTS_PER_COLLECTION_COUNT):
            collection.reports.add(SavedReportFactory.create())


class Command(BaseCommand):
    help = "Populates development database with example data."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **options):
        if options["reset"]:
            call_command("reset_db", "--noinput")  # needs django_extensions installed
            call_command("migrate")

        do_populate = True
        if User.objects.count() > 0:
            print("Development database already populated. Skipping.")
            do_populate = False

        if do_populate:
            print("Populating development database with test data.")

            users = create_users()
            create_report_collections(users)
