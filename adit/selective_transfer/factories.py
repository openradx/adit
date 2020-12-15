import factory
from faker import Faker
from adit.core.factories import DicomFolderFactory
from adit.core.factories import TransferJobFactory
from .models import SelectiveTransferJob

fake = Faker()


def generate_archive_password():
    if fake.boolean(chance_of_getting_true=25):
        return fake.word()
    return ""


class SelectiveTransferJobFactory(TransferJobFactory):
    class Meta:
        model = SelectiveTransferJob

    archive_password = factory.LazyFunction(generate_archive_password)


class SelectiveTransferJobToPathFactory(SelectiveTransferJobFactory):
    destination = factory.SubFactory(DicomFolderFactory)
