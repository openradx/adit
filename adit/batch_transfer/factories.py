import factory
from faker import Faker

from adit.core.factories import (
    DicomFolderFactory,
    TransferJobFactory,
    TransferTaskFactory,
)

from .models import BatchTransferJob, BatchTransferTask

fake = Faker()


class BatchTransferJobFactory(TransferJobFactory):
    class Meta:
        model = BatchTransferJob

    project_name = factory.Faker("sentence")
    project_description = factory.Faker("paragraph")


class BatchTransferJobToPathFactory(BatchTransferJobFactory):
    destination = factory.SubFactory(DicomFolderFactory)


class BatchTransferTaskFactory(TransferTaskFactory):
    class Meta:
        model = BatchTransferTask

    job = factory.SubFactory(BatchTransferJobFactory)
