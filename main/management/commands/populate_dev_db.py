from django.core.management.base import BaseCommand
import factory
from django.contrib.auth.models import Group
from accounts.factories import AdminUserFactory, UserFactory
from main.factories import DicomServerFactory, DicomFolderFactory
from batch_transfer.factories import (
        BatchTransferJobFactory, BatchTransferRequestFactory)

class Command(BaseCommand):
    help = 'Copies vendor files from node_modues folder'

    def handle(self, *args, **options):
        admin = AdminUserFactory()

        batch_transferrers_group = Group.objects.get(name='batch_transferrers')

        users = [admin]
        for i in range(10):
            user = UserFactory()
            user.groups.add(batch_transferrers_group)
            users.append(user)
            
        servers = []
        servers.append(DicomServerFactory(
            node_name='Orthac Test Server 1',
            ae_title='ORTHANC1',
            ip='127.0.0.1',
            port=7501
        ))
        servers.append(DicomServerFactory(
            node_name='Orthac Test Server 2',
            ae_title='ORTHANC2',
            ip='127.0.0.1',
            port=7502
        ))

        folders = []
        folders.append(DicomFolderFactory(
            node_name='tmp folder',
            path='/tmp/adit_dicom_folder'
        ))

        servers_and_folders = servers + folders

        batch_transfer_jobs = []
        for i in range(150):
            batch_transfer_jobs.append(BatchTransferJobFactory(
                source=factory.Faker('random_element', elements=servers),
                destination=factory.Faker('random_element', elements=servers_and_folders),
                created_by=factory.Faker('random_element', elements=users)
            ))

        batch_transfer_requests = []
        for i in range(500):
            batch_transfer_requests.append(BatchTransferRequestFactory(
                job=factory.Faker('random_element', elements=batch_transfer_jobs)
            ))