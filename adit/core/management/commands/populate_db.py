from os import environ

from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandParser
from faker import Faker

from adit.accounts.factories import AdminUserFactory, InstituteFactory, UserFactory
from adit.accounts.models import Institute, User

USER_COUNT = 20
INSTITUTE_COUNT = 3
DICOM_SERVER_COUNT = 5
DICOM_FOLDER_COUNT = 3
SELECTIVE_TRANSFER_JOB_COUNT = 20
BATCH_QUERY_JOB_COUNT = 10
BATCH_TRANSFER_JOB_COUNT = 10

fake = Faker()


def create_users() -> list[User]:
    if "ADMIN_USERNAME" not in environ or "ADMIN_PASSWORD" not in environ:
        print("Cave! No admin credentials found in environment. Using default ones.")

    admin_data = {
        "username": environ.get("ADMIN_USERNAME", "admin"),
        "first_name": environ.get("ADMIN_FIRST_NAME", "Wilhelm"),
        "last_name": environ.get("ADMIN_LAST_NAME", "Röntgen"),
        "email": environ.get("ADMIN_EMAIL", "wilhelm.roentgen@example.org"),
        "password": environ.get("ADMIN_PASSWORD", "mysecret"),
    }
    admin = AdminUserFactory.create(**admin_data)

    batch_transfer_group = Group.objects.get(name="batch_transfer_group")
    selective_transfer_group = Group.objects.get(name="selective_transfer_group")

    users = [admin]

    urgent_permissions = Permission.objects.filter(
        codename="can_process_urgently",
    )
    unpseudonymized_permissions = Permission.objects.filter(
        codename="can_transfer_unpseudonymized",
    )

    user_count = USER_COUNT - 1  # -1 for admin
    for i in range(user_count):
        user = UserFactory.create()
        user.groups.add(batch_transfer_group)
        user.groups.add(selective_transfer_group)

        if i > 0:
            user.user_permissions.add(*urgent_permissions)
            user.user_permissions.add(*unpseudonymized_permissions)

        users.append(user)

    return users


def create_institutes(users: list[User]) -> list[Institute]:
    institutes: list[Institute] = []

    for _ in range(INSTITUTE_COUNT):
        institute = InstituteFactory.create()
        institutes.append(institute)

    for user in users:
        institute: Institute = fake.random_element(elements=institutes)
        institute.users.add(user)

    return institutes


class Command(BaseCommand):
    help = "Populates the database with example data."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **options):
        if options["reset"]:
            # Can only be done when dev server is not running and needs django_extensions installed
            call_command("reset_db", "--noinput")
            call_command("migrate")

        do_populate = True
        if User.objects.count() > 0:
            print("Development database already populated. Skipping.")
            do_populate = False

        if do_populate:
            print("Populating development database with test data.")

            users = create_users()
            create_institutes(users)
