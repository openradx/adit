from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import DetailView
from django.conf import settings
from adit.main.mixins import OwnerRequiredMixin
from adit.main.views import InlineFormSetCreateView
from .models import ContinuousTransferJob
from .forms import (
    ContinuousTransferJobForm,
    DataElementFilterFormSet,
    DataElementFilterFormSetHelper,
)


def clear_errors(form_or_formset):
    # Hide all errors as we only add another form.
    # Found only this hacky way.
    # See https://stackoverflow.com/questions/64402527
    # pylint: disable=protected-access
    form_or_formset._errors = {}
    if hasattr(form_or_formset, "forms"):
        for form in form_or_formset.forms:
            clear_errors(form)


class ContinuousTransferJobCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, InlineFormSetCreateView
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
