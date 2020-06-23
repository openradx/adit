from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import CreateView
from django.views.generic import DetailView
from .models import BatchTransferJob
from .forms import BatchTransferJobForm

class BatchTransferJobCreate(LoginRequiredMixin, CreateView):
    model = BatchTransferJob
    form_class = BatchTransferJobForm
    template_name = 'batch_transfer/batch_transfer_job_form.html'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class BatchTransferJobDetail(LoginRequiredMixin, DetailView):
    model = BatchTransferJob
    context_object_name = 'job'
    template_name = 'batch_transfer/batch_transfer_job_detail.html'