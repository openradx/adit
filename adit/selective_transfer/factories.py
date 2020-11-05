import factory
from adit.core.factories import DicomFolderFactory
from adit.core.factories import TransferJobFactory
from .models import SelectiveTransferJob


class SelectiveTransferJobFactory(TransferJobFactory):
    class Meta:
        model = SelectiveTransferJob

    job_type = SelectiveTransferJob.JOB_TYPE


class SelectiveTransferJobToPathFactory(SelectiveTransferJobFactory):
    destination = factory.SubFactory(DicomFolderFactory)
