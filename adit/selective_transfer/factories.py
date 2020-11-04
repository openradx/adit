import factory
from adit.core.factories import DicomFolderFactory
from adit.core.factories import TransferJobFactory
from .models import SelectiveTransferJob


class SelectiveTransferJobFactory(TransferJobFactory):
    class Meta:
        model = SelectiveTransferJob


class SelectiveTransferJobToPathFactory(SelectiveTransferJobFactory):
    destination = factory.SubFactory(DicomFolderFactory)
