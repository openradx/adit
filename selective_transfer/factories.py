import factory
from main.factories import DicomFolderFactory
from main.factories import TransferJobFactory
from .models import SelectiveTransferJob


class SelectiveTransferJobFactory(TransferJobFactory):
    class Meta:
        model = SelectiveTransferJob


class SelectiveTransferJobToPathFactory(SelectiveTransferJobFactory):
    destination = factory.SubFactory(DicomFolderFactory)
