from django.views.generic.edit import CreateView
from .models import BatchTransferJob
from .forms import BatchTransferJobForm

class BatchTransferJobCreate(CreateView):
    model = BatchTransferJob
    form_class = BatchTransferJobForm
