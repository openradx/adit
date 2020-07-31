from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic.edit import CreateView, FormView
from django.views.generic import DetailView
from main.mixins import OwnerRequiredMixin
from .forms import QueryStudiesForm
from .models import SelectiveTransferJob


class QueryStudiesView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = "selective_transfer/query_studies_form.html"
    form_class = QueryStudiesForm
    permission_required = "selective_transfer.add_selectivetransferjob"


class SelectiveTransferJobCreate(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = SelectiveTransferJob


class SelectiveTransferJobDetail(LoginRequiredMixin, OwnerRequiredMixin, DetailView):
    model = SelectiveTransferJob
    context_object_name = "job"
    template_name = "selective_transfer/selective_transfer_job_detail.html"
    owner_accessor = "created_by"
