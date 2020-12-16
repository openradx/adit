from os import environ
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from faker import Faker
import factory

# pylint: disable=import-error,no-name-in-module
from adit.accounts.models import User
from adit.accounts.factories import AdminUserFactory, UserFactory
from adit.core.factories import (
    DicomServerFactory,
    DicomFolderFactory,
)
from adit.batch_transfer.factories import (
    BatchTransferJobFactory,
    BatchTransferRequestFactory,
    BatchTransferTaskFactory,
)
from adit.selective_transfer.factories import (
    SelectiveTransferJobFactory,
    SelectiveTransferTaskFactory,
)

CREATE_JOBS_FOR_ADMIN_ONLY = True
PROBABILITY_OF_BATCH_JOB = 50

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

    batch_transferrers_group = Group.objects.get(name="batch_transferrers")
    selective_transferrers_group = Group.objects.get(name="selective_transferrers")

    users = [admin]
    for _ in range(10):
        user = UserFactory()
        user.groups.add(batch_transferrers_group)
        user.groups.add(selective_transferrers_group)
        users.append(user)

    return users


def create_server_nodes():
    servers = []
    orthanc1_host = environ.get("ORTHANC1_HOST", "127.0.0.1")
    servers.append(
        DicomServerFactory(
            name="Orthanc Test Server 1",
            ae_title="ORTHANC1",
            host=orthanc1_host,
            port=7501,
        )
    )
    orthanc2_host = environ.get("ORTHANC2_HOST", "127.0.0.1")
    servers.append(
        DicomServerFactory(
            name="Orthanc Test Server 2",
            ae_title="ORTHANC2",
            host=orthanc2_host,
            port=7502,
        )
    )
    return servers


def create_folder_nodes():
    folders = []
    folders.append(DicomFolderFactory(name="tmp folder", path="/tmp/adit_dicom_folder"))
    return folders


def create_jobs(users, servers, folders):
    for _ in range(10):
        if fake.boolean(chance_of_getting_true=PROBABILITY_OF_BATCH_JOB):
            create_batch_transfer_job(users, servers, folders)
        else:
            create_selective_transfer_job(users, servers, folders)


def create_batch_transfer_job(users, servers, folders):
    servers_and_folders = servers + folders

    job = BatchTransferJobFactory(
        source=factory.Faker("random_element", elements=servers),
        destination=factory.Faker("random_element", elements=servers_and_folders),
        owner=factory.Faker("random_element", elements=users),
    )

    for row_number in range(fake.random_int(min=1, max=100)):
        request = BatchTransferRequestFactory(job=job, row_number=row_number)

        for _ in range(fake.random_int(min=1, max=3)):
            BatchTransferTaskFactory(request=request, job=job)

    return job


def create_selective_transfer_job(users, servers, folders):
    servers_and_folders = servers + folders

    job = SelectiveTransferJobFactory(
        source=factory.Faker("random_element", elements=servers),
        destination=factory.Faker("random_element", elements=servers_and_folders),
        owner=factory.Faker("random_element", elements=users),
    )

    for _ in range(fake.random_int(min=1, max=120)):
        SelectiveTransferTaskFactory(job=job)


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

            if CREATE_JOBS_FOR_ADMIN_ONLY:
                users = [users[0]]

            create_jobs(users, servers, folders)
