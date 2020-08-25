from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from faker import Faker
import factory

# pylint: disable=import-error,no-name-in-module
from accounts.factories import AdminUserFactory, UserFactory
from main.factories import DicomServerFactory, DicomFolderFactory, TransferTaskFactory
from batch_transfer.factories import (
    BatchTransferJobFactory,
    BatchTransferRequestFactory,
)
from selective_transfer.factories import SelectiveTransferJobFactory

fake = Faker()


def create_users():
    admin = AdminUserFactory()

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
    servers.append(
        DicomServerFactory(
            node_name="Orthac Test Server 1",
            ae_title="ORTHANC1",
            ip="127.0.0.1",
            port=7501,
        )
    )
    servers.append(
        DicomServerFactory(
            node_name="Orthac Test Server 2",
            ae_title="ORTHANC2",
            ip="127.0.0.1",
            port=7502,
        )
    )
    return servers


def create_folder_nodes():
    folders = []
    folders.append(
        DicomFolderFactory(node_name="tmp folder", path="/tmp/adit_dicom_folder")
    )
    return folders


def create_jobs(users, servers, folders):
    for _ in range(110):
        if fake.boolean(chance_of_getting_true=25):
            create_batch_transfer_job(users, servers, folders)
        else:
            create_selective_transfer_job(users, servers, folders)


def create_batch_transfer_job(users, servers, folders):
    servers_and_folders = servers + folders

    job = BatchTransferJobFactory(
        source=factory.Faker("random_element", elements=servers),
        destination=factory.Faker("random_element", elements=servers_and_folders),
        created_by=factory.Faker("random_element", elements=users),
    )

    for _ in range(fake.random_int(min=0, max=200)):
        request = BatchTransferRequestFactory(job=job)

        for _ in range(fake.random_int(min=0, max=3)):
            TransferTaskFactory(content_object=request, job=job)

    return job


def create_selective_transfer_job(users, servers, folders):
    servers_and_folders = servers + folders

    job = SelectiveTransferJobFactory(
        source=factory.Faker("random_element", elements=servers),
        destination=factory.Faker("random_element", elements=servers_and_folders),
        created_by=factory.Faker("random_element", elements=users),
    )

    for _ in range(fake.random_int(min=0, max=120)):
        TransferTaskFactory(job=job)


class Command(BaseCommand):
    help = "Copies vendor files from node_modues folder"

    def handle(self, *args, **options):
        users = create_users()
        servers = create_server_nodes()
        folders = create_folder_nodes()
        create_jobs(users, servers, folders)
