from adit.core.views import DicomJobCancelView

from .models import ExampleTransferJob


class ExampleTransferJobCancelView(DicomJobCancelView):
    model = ExampleTransferJob
