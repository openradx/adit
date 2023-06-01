import factory
from faker import Faker

from adit.core.factories import (
    AbstractTransferJobFactory,
    AbstractTransferTaskFactory,
    DicomFolderFactory,
)

from .models import BatchTransferJob, BatchTransferTask

fake = Faker()


class BatchTransferJobFactory(AbstractTransferJobFactory[BatchTransferJob]):
    class Meta:
        model = BatchTransferJob

    project_name = factory.Faker("sentence")
    project_description = factory.Faker("paragraph")


class BatchTransferJobToPathFactory(BatchTransferJobFactory):
    destination = factory.SubFactory(DicomFolderFactory)


class BatchTransferTaskFactory(AbstractTransferTaskFactory[BatchTransferTask]):
    class Meta:
        model = BatchTransferTask

    job = factory.SubFactory(BatchTransferJobFactory)
