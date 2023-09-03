from os import environ

import factory
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandParser
from faker import Faker

from adit.accounts.factories import AdminUserFactory, InstituteFactory, UserFactory
from adit.accounts.models import Institute, User
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
    DicomNodeInstituteAccessFactory,
    DicomServerFactory,
)
from adit.core.models import DicomFolder, DicomServer
from adit.selective_transfer.factories import (
    SelectiveTransferJobFactory,
    SelectiveTransferTaskFactory,
)

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


def create_server_nodes(institutes: list[Institute]) -> list[DicomServer]:
    servers: list[DicomServer] = []

    orthanc1 = DicomServerFactory.create(
        name="Orthanc Test Server 1",
        ae_title="ORTHANC1",
        host=settings.ORTHANC1_HOST,
        port=settings.ORTHANC1_DICOM_PORT,
    )

    servers.append(orthanc1)

    DicomNodeInstituteAccessFactory.create(
        dicom_node=orthanc1,
        institute=institutes[0],
        source=True,
        destination=True,
    )

    orthanc2 = DicomServerFactory.create(
        name="Orthanc Test Server 2",
        ae_title="ORTHANC2",
        host=settings.ORTHANC2_HOST,
        port=settings.ORTHANC2_DICOM_PORT,
    )

    servers.append(orthanc2)

    DicomNodeInstituteAccessFactory.create(
        dicom_node=orthanc2,
        institute=institutes[0],
        destination=True,
    )

    server_count = DICOM_SERVER_COUNT - 2  # -2 for Orthanc servers
    for _ in range(server_count):
        server = DicomServerFactory.create()
        servers.append(server)

        DicomNodeInstituteAccessFactory.create(
            dicom_node=server,
            institute=fake.random_element(elements=institutes),
            source=fake.boolean(),
            destination=fake.boolean(),
        )

    return servers


def create_folder_nodes(institutes: list[Institute]) -> list[DicomFolder]:
    folders: list[DicomFolder] = []

    download_folder = DicomFolderFactory.create(name="Downloads", path="/app/dicom_downloads")
    folders.append(download_folder)

    DicomNodeInstituteAccessFactory.create(
        dicom_node=download_folder,
        institute=institutes[0],
        destination=True,
    )

    folder_count = DICOM_FOLDER_COUNT - 1  # -1 for Downloads folder
    for _ in range(folder_count):
        folder = DicomFolderFactory.create()
        folders.append(folder)

        DicomNodeInstituteAccessFactory.create(
            dicom_node=folder,
            institute=fake.random_element(elements=institutes),
            destination=True,
        )

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

    job = SelectiveTransferJobFactory.create(
        source=factory.Faker("random_element", elements=servers),
        destination=factory.Faker("random_element", elements=servers_and_folders),
        owner=factory.Faker("random_element", elements=users),
    )

    for task_id in range(fake.random_int(min=1, max=100)):
        SelectiveTransferTaskFactory.create(job=job, task_id=task_id)


def create_batch_transfer_job(
    users: list[User], servers: list[DicomServer], folders: list[DicomFolder]
) -> None:
    servers_and_folders = servers + folders

    job = BatchTransferJobFactory.create(
        source=factory.Faker("random_element", elements=servers),
        destination=factory.Faker("random_element", elements=servers_and_folders),
        owner=factory.Faker("random_element", elements=users),
    )

    for task_id in range(fake.random_int(min=1, max=100)):
        BatchTransferTaskFactory.create(job=job, task_id=task_id)


def create_batch_query_job(users: list[User], servers: list[DicomServer]) -> None:
    job = BatchQueryJobFactory.create(
        source=factory.Faker("random_element", elements=servers),
        owner=factory.Faker("random_element", elements=users),
    )

    for task_id in range(fake.random_int(min=1, max=100)):
        query = BatchQueryTaskFactory.create(job=job, task_id=task_id)

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
            institutes = create_institutes(users)
            servers = create_server_nodes(institutes)
            folders = create_folder_nodes(institutes)

            create_jobs(users, servers, folders)
