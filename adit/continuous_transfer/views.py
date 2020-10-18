import re
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic.edit import CreateView
from django.views.generic import DetailView
from django.conf import settings
from adit.main.mixins import OwnerRequiredMixin
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
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = ContinuousTransferJob
    form_class = ContinuousTransferJobForm
    template_name = "continuous_transfer/continuous_transfer_job_form.html"
    permission_required = "continuous_transfer.add_continuoustransferjob"

    def add_formset_form(self, prefix):
        cp = self.request.POST.copy()
        cp[f"{prefix}-TOTAL_FORMS"] = int(cp[f"{prefix}-TOTAL_FORMS"]) + 1
        return cp

    def delete_formset_form(self, num_to_delete, prefix):
        cp = self.request.POST.copy()
        cp[f"{prefix}-TOTAL_FORMS"] = int(cp[f"{prefix}-TOTAL_FORMS"]) - 1
        regex = prefix + r"-(\d+)-"
        filtered = {}
        for k, v in cp.items():
            match = re.findall(regex, k)
            if match:
                num = int(match[0])
                if num == num_to_delete:
                    continue
                if num > num_to_delete:
                    k = re.sub(regex, f"{prefix}-{num-1}-", k)
                filtered[k] = v
            else:
                filtered[k] = v
        return filtered

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data["helper"] = DataElementFilterFormSetHelper()

        if self.request.POST:
            if self.request.POST.get("add_filter"):
                post_data = self.add_formset_form("filters")
                filters = DataElementFilterFormSet(post_data)
                data["filters"] = filters
                clear_errors(data["form"])
                clear_errors(data["filters"])
            elif self.request.POST.get("delete_filter"):
                num_to_delete = int(self.request.POST.get("delete_filter"))
                post_data = self.delete_formset_form(num_to_delete, "filters")
                filters = DataElementFilterFormSet(post_data)
                data["filters"] = filters
                clear_errors(data["form"])
                clear_errors(data["filters"])
            else:
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
