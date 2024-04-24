from os import environ

import factory
from adit_radis_shared.accounts.factories import AdminUserFactory, GroupFactory, UserFactory
from adit_radis_shared.accounts.models import User
from adit_radis_shared.token_authentication.factories import TokenFactory
from adit_radis_shared.token_authentication.models import FRACTION_LENGTH
from adit_radis_shared.token_authentication.utils.crypto import hash_token
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandParser
from faker import Faker

from adit.batch_query.factories import (
    BatchQueryJobFactory,
    BatchQueryResultFactory,
    BatchQueryTaskFactory,
)
from adit.batch_transfer.factories import (
    BatchTransferJobFactory,
    BatchTransferTaskFactory,
)
from adit.core.factories import (
    DicomFolderFactory,
    DicomServerFactory,
)
from adit.core.models import DicomFolder, DicomServer
from adit.core.utils.auth_utils import grant_access
from adit.selective_transfer.factories import (
    SelectiveTransferJobFactory,
    SelectiveTransferTaskFactory,
)

USER_COUNT = 20
GROUP_COUNT = 3
DICOM_SERVER_COUNT = 5
DICOM_FOLDER_COUNT = 3
SELECTIVE_TRANSFER_JOB_COUNT = 20
BATCH_QUERY_JOB_COUNT = 10
BATCH_TRANSFER_JOB_COUNT = 10

fake = Faker()


def create_admin() -> User:
    if "ADMIN_USERNAME" not in environ or "ADMIN_PASSWORD" not in environ:
        print("Cave! No admin credentials found in environment. Using default ones.")

    admin = AdminUserFactory.create(
        username=environ.get("ADMIN_USERNAME", "admin"),
        first_name=environ.get("ADMIN_FIRST_NAME", "Wilhelm"),
        last_name=environ.get("ADMIN_LAST_NAME", "Röntgen"),
        email=environ.get("ADMIN_EMAIL", "wilhelm.roentgen@example.org"),
        password=environ.get("ADMIN_PASSWORD", "mysecret"),
    )

    if "ADMIN_AUTH_TOKEN" not in environ:
        print("No admin auth token in environment. Skipping auth token creation.")
    else:
        auth_token = environ["ADMIN_AUTH_TOKEN"]
        TokenFactory.create(
            token_hashed=hash_token(auth_token),
            fraction=auth_token[:FRACTION_LENGTH],
            owner=admin,
            expires=None,
        )

    return admin


def create_users() -> list[User]:
    admin = create_admin()

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

        if i > 0:
            user.user_permissions.add(*urgent_permissions)
            user.user_permissions.add(*unpseudonymized_permissions)

        users.append(user)

    return users


def create_groups(users: list[User]) -> list[Group]:
    groups: list[Group] = []

    for _ in range(GROUP_COUNT):
        group = GroupFactory.create()
        groups.append(group)

    for user in users:
        group: Group = fake.random_element(elements=groups)
        user.groups.add(group)
        if not user.active_group:
            user.change_active_group(group)

    return groups


def create_server_nodes(groups: list[Group]) -> list[DicomServer]:
    servers: list[DicomServer] = []

    orthanc1 = DicomServerFactory.create(
        name="Orthanc Test Server 1",
        ae_title="ORTHANC1",
        host=settings.ORTHANC1_HOST,
        port=settings.ORTHANC1_DICOM_PORT,
    )
    grant_access(groups[0], orthanc1, source=True, destination=True)
    servers.append(orthanc1)

    orthanc2 = DicomServerFactory.create(
        name="Orthanc Test Server 2",
        ae_title="ORTHANC2",
        host=settings.ORTHANC2_HOST,
        port=settings.ORTHANC2_DICOM_PORT,
    )
    grant_access(groups[0], orthanc2, destination=True)
    servers.append(orthanc2)

    server_count = DICOM_SERVER_COUNT - 2  # -2 for Orthanc servers
    for _ in range(server_count):
        server = DicomServerFactory.create()
        grant_access(
            fake.random_element(elements=groups),
            server,
            source=fake.boolean(),
            destination=fake.boolean(),
        )
        servers.append(server)

    return servers


def create_folder_nodes(groups: list[Group]) -> list[DicomFolder]:
    folders: list[DicomFolder] = []

    download_folder = DicomFolderFactory.create(name="Downloads", path="/app/dicom_downloads")
    grant_access(groups[0], download_folder, destination=True)
    folders.append(download_folder)

    folder_count = DICOM_FOLDER_COUNT - 1  # -1 for Downloads folder
    for _ in range(folder_count):
        folder = DicomFolderFactory.create()
        grant_access(fake.random_element(elements=groups), folder, destination=True)
        folders.append(folder)

    return folders


def create_jobs(users: list[User], servers: list[DicomServer], folders: list[DicomFolder]) -> None:
    for _ in range(SELECTIVE_TRANSFER_JOB_COUNT):
        create_selective_transfer_job(users, servers, folders)

    for _ in range(BATCH_TRANSFER_JOB_COUNT):
        create_batch_transfer_job(users, servers, folders)

    for _ in range(BATCH_QUERY_JOB_COUNT):
        create_batch_query_job(users, servers)


def create_selective_transfer_job(
    users: list[User], servers: list[DicomServer], folders: list[DicomFolder]
) -> None:
    servers_and_folders = servers + folders

    job = SelectiveTransferJobFactory.create(owner=factory.Faker("random_element", elements=users))

    for _ in range(fake.random_int(min=1, max=100)):
        SelectiveTransferTaskFactory.create(
            job=job,
            source=factory.Faker("random_element", elements=servers),
            destination=factory.Faker("random_element", elements=servers_and_folders),
        )


def create_batch_transfer_job(
    users: list[User], servers: list[DicomServer], folders: list[DicomFolder]
) -> None:
    servers_and_folders = servers + folders

    job = BatchTransferJobFactory.create(owner=factory.Faker("random_element", elements=users))

    for _ in range(fake.random_int(min=1, max=100)):
        BatchTransferTaskFactory.create(
            job=job,
            source=factory.Faker("random_element", elements=servers),
            destination=factory.Faker("random_element", elements=servers_and_folders),
        )


def create_batch_query_job(users: list[User], servers: list[DicomServer]) -> None:
    job = BatchQueryJobFactory.create(owner=factory.Faker("random_element", elements=users))

    for _ in range(fake.random_int(min=1, max=100)):
        query = BatchQueryTaskFactory.create(
            job=job,
            source=factory.Faker("random_element", elements=servers),
        )

        for _ in range(fake.random_int(min=1, max=3)):
            BatchQueryResultFactory.create(job=job, query=query)


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
            groups = create_groups(users)
            servers = create_server_nodes(groups)
            folders = create_folder_nodes(groups)

            create_jobs(users, servers, folders)
