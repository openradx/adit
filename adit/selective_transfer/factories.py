import factory
from adit.main.factories import DicomFolderFactory
from adit.main.factories import TransferJobFactory
from .models import SelectiveTransferJob


class SelectiveTransferJobFactory(TransferJobFactory):
    class Meta:
        model = SelectiveTransferJob


class SelectiveTransferJobToPathFactory(SelectiveTransferJobFactory):
    destination = factory.SubFactory(DicomFolderFactory)
