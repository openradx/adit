import factory
from faker import Faker

from adit.core.factories import (
    AbstractTransferJobFactory,
    AbstractTransferTaskFactory,
    DicomFolderFactory,
)

from .models import SelectiveTransferJob, SelectiveTransferTask

fake = Faker()


def generate_archive_password():
    if fake.boolean(chance_of_getting_true=25):
        return fake.word()
    return ""


class SelectiveTransferJobFactory(AbstractTransferJobFactory[SelectiveTransferJob]):
    class Meta:
        model = SelectiveTransferJob

    archive_password = factory.LazyFunction(generate_archive_password)


class SelectiveTransferJobToPathFactory(SelectiveTransferJobFactory):
    destination = factory.SubFactory(DicomFolderFactory)


class SelectiveTransferTaskFactory(AbstractTransferTaskFactory[SelectiveTransferTask]):
    class Meta:
        model = SelectiveTransferTask

    job = factory.SubFactory(SelectiveTransferJobFactory)
