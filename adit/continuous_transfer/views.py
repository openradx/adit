from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import DetailView
from django.conf import settings
from django.urls import reverse_lazy
from adit.core.mixins import OwnerRequiredMixin, TransferFormViewMixin
from adit.core.views import (
    TransferJobListView,
    DicomJobDeleteView,
    DicomJobCancelView,
    DicomJobVerifyView,
    TransferTaskDetailView,
)
from adit.core.views import InlineFormSetCreateView
from .models import ContinuousTransferJob, ContinuousTransferTask
from .forms import (
    ContinuousTransferJobForm,
    DataElementFilterFormSet,
    DataElementFilterFormSetHelper,
)
from .tables import ContinuousTransferJobTable
from .filters import ContinuousTransferJobFilter


class ContinuousTransferJobListView(
    TransferJobListView
):  # pylint: disable=too-many-ancestors
    model = ContinuousTransferJob
    table_class = ContinuousTransferJobTable
    filterset_class = ContinuousTransferJobFilter

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["job_list_title"] = "Continuous Transfer Jobs"
        return context


class ContinuousTransferJobCreateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    TransferFormViewMixin,
    InlineFormSetCreateView,
):
    model = ContinuousTransferJob
    form_class = ContinuousTransferJobForm
    template_name = "continuous_transfer/continuous_transfer_job_form.html"
    permission_required = "continuous_transfer.add_continuoustransferjob"
    formset_class = DataElementFilterFormSet
    formset_prefix = "filters"

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data["helper"] = DataElementFilterFormSetHelper()
        return data

    def form_and_formset_valid(self, form, formset):
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


class ContinuousTransferJobDeleteView(DicomJobDeleteView):
    model = ContinuousTransferJob
    success_url = reverse_lazy("continuous_transfer_job_list")


class ContinuousTransferJobCancelView(DicomJobCancelView):
    model = ContinuousTransferJob


class ContinuousTransferJobVerifyView(DicomJobVerifyView):
    model = ContinuousTransferJob


class ContinuousTransferTaskDetailView(TransferTaskDetailView):
    model = ContinuousTransferTask
