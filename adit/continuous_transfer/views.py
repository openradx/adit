from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic.edit import CreateView
from django.views.generic import DetailView
from django.conf import settings
from adit.main.mixins import OwnerRequiredMixin
from .models import ContinuousTransferJob
from .forms import ContinuousTransferJobForm, DataElementFilterFormSet


class ContinuousTransferJobCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = ContinuousTransferJob
    form_class = ContinuousTransferJobForm
    template_name = "continuous_transfer/continuous_transfer_job_form.html"
    permission_required = "continuous_transfer.add_continuoustransferjob"

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data["filters"] = DataElementFilterFormSet(self.request.POST)
        else:
            data["filters"] = DataElementFilterFormSet()
        return data

    def form_valid(self, form):
        user = self.request.user
        form.instance.owner = user
        response = super().form_valid(form)

        job = self.object
        if user.is_staff or settings.CONTINUOUS_TRANSFER_UNVERIFIED:
            job.status = ContinuousTransferJob.Status.PENDING
            job.save()
            job.delay()

        return response


class ContinuousTransferJobDetailView(
    LoginRequiredMixin, OwnerRequiredMixin, DetailView
):
    model = ContinuousTransferJob
    context_object_name = "job"
    template_name = "continuous_transfer/continuous_transfer_job_detail.html"
    owner_accessor = "owner"
