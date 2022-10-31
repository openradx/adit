from os import environ
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, Group
from django.conf import settings
from faker import Faker
import factory

from adit.accounts.models import User
from adit.accounts.factories import AdminUserFactory, UserFactory
from adit.core.factories import (
    DicomServerFactory,
    DicomFolderFactory,
)
from adit.batch_transfer.factories import (
    BatchTransferJobFactory,
    BatchTransferTaskFactory,
)
from adit.selective_transfer.factories import (
    SelectiveTransferJobFactory,
    SelectiveTransferTaskFactory,
)
from adit.batch_query.factories import (
    BatchQueryJobFactory,
    BatchQueryTaskFactory,
    BatchQueryResultFactory,
)


USER_COUNT = 3
SELECTIVE_TRANSFER_JOB_COUNT = 5
BATCH_TRANSFER_JOB_COUNT = 3
BATCH_QUERY_JOB_COUNT = 2

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
    admin = AdminUserFactory(**admin_data)

    batch_transfer_group = Group.objects.get(name="batch_transfer_group")
    selective_transfer_group = Group.objects.get(name="selective_transfer_group")

    users = [admin]

    urgent_permissions = Permission.objects.filter(
        codename="can_process_urgently",
    )
    unpseudonymized_permissions = Permission.objects.filter(
        codename="can_transfer_unpseudonymized",
    )

    for i in range(USER_COUNT):
        user = UserFactory()
        user.groups.add(batch_transfer_group)
        user.groups.add(selective_transfer_group)

        if i > 0:
            user.user_permissions.add(*urgent_permissions)
            user.user_permissions.add(*unpseudonymized_permissions)

        users.append(user)

    return users


def create_server_nodes():
    servers = []
    servers.append(
        DicomServerFactory(
            name="Orthanc Test Server 1",
            ae_title="ORTHANC1",
            host=settings.ORTHANC1_HOST,
            port=settings.ORTHANC1_DICOM_PORT,
            patient_root_find_support=True,
            patient_root_get_support=True,
            patient_root_move_support=True,
            study_root_find_support=True,
            study_root_get_support=True,
            study_root_move_support=True,
            store_scp_support=True,
        )
    )
    servers.append(
        DicomServerFactory(
            name="Orthanc Test Server 2",
            ae_title="ORTHANC2",
            host=settings.ORTHANC2_HOST,
            port=settings.ORTHANC2_DICOM_PORT,
            patient_root_find_support=True,
            patient_root_get_support=True,
            patient_root_move_support=True,
            study_root_find_support=True,
            study_root_get_support=True,
            study_root_move_support=True,
            store_scp_support=True,
        )
    )
    return servers


def create_folder_nodes():
    folders = []
    folders.append(DicomFolderFactory(name="Downloads", path="/app/dicom_downloads"))
    return folders


def create_jobs(users, servers, folders):
    for _ in range(SELECTIVE_TRANSFER_JOB_COUNT):
        create_selective_transfer_job(users, servers, folders)

    for _ in range(BATCH_TRANSFER_JOB_COUNT):
        create_batch_transfer_job(users, servers, folders)

    for _ in range(BATCH_QUERY_JOB_COUNT):
        create_batch_query_job(users)


def create_selective_transfer_job(users, servers, folders):
    servers_and_folders = servers + folders

    job = SelectiveTransferJobFactory(
        source=factory.Faker("random_element", elements=servers),
        destination=factory.Faker("random_element", elements=servers_and_folders),
        owner=factory.Faker("random_element", elements=users),
    )

    for task_id in range(fake.random_int(min=1, max=100)):
        SelectiveTransferTaskFactory(job=job, task_id=task_id)


def create_batch_transfer_job(users, servers, folders):
    servers_and_folders = servers + folders

    job = BatchTransferJobFactory(
        source=factory.Faker("random_element", elements=servers),
        destination=factory.Faker("random_element", elements=servers_and_folders),
        owner=factory.Faker("random_element", elements=users),
    )

    for task_id in range(fake.random_int(min=1, max=100)):
        BatchTransferTaskFactory(job=job, task_id=task_id)

    return job


def create_batch_query_job(users):
    job = BatchQueryJobFactory(
        owner=factory.Faker("random_element", elements=users),
    )

    for task_id in range(fake.random_int(min=1, max=100)):
        query = BatchQueryTaskFactory(job=job, task_id=task_id)

        for _ in range(fake.random_int(min=1, max=3)):
            BatchQueryResultFactory(job=job, query=query)

    return job


class Command(BaseCommand):
    help = "Copies vendor files from node_modues folder"

    def handle(self, *args, **options):
        do_populate = True
        if User.objects.count() > 0:
            print("Development database already populated. Skipping.")
            do_populate = False

        if do_populate:
            print("Populating development database with test data.")

            users = create_users()
            servers = create_server_nodes()
            folders = create_folder_nodes()

            create_jobs(users, servers, folders)
