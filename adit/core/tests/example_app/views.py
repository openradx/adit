from adit.core.views import DicomJobCancelView, DicomJobDeleteView

from .models import ExampleTransferJob


class ExampleTransferJobDeleteView(DicomJobDeleteView):
    model = ExampleTransferJob
    success_url = "/"


class ExampleTransferJobCancelView(DicomJobCancelView):
    model = ExampleTransferJob
