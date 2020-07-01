from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import CreateView
from django.views.generic import DetailView
from django.contrib.auth.mixins import PermissionRequiredMixin
from main.mixins import OwnerRequiredMixin
from .models import BatchTransferJob
from .forms import BatchTransferJobForm

class BatchTransferJobCreate(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = BatchTransferJob
    form_class = BatchTransferJobForm
    template_name = 'batch_transfer/batch_transfer_job_form.html'
    permission_required = 'batch_transfer.add_batchtransferjob'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'user': self.request.user})
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

class BatchTransferJobDetail(LoginRequiredMixin, OwnerRequiredMixin, DetailView):
    model = BatchTransferJob
    context_object_name = 'job'
    template_name = 'batch_transfer/batch_transfer_job_detail.html'
    owner_accessor = 'created_by'