from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic.edit import CreateView
from django.views.generic import DetailView
from main.mixins import OwnerRequiredMixin
from .forms import SelectiveTransferJobForm
from .models import SelectiveTransferJob


class SelectiveTransferJobCreate(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    template_name = "selective_transfer/selective_transfer_job_form.html"
    form_class = SelectiveTransferJobForm
    permission_required = "selective_transfer.add_selectivetransferjob"



class SelectiveTransferJobDetail(LoginRequiredMixin, OwnerRequiredMixin, DetailView):
    model = SelectiveTransferJob
    context_object_name = "job"
    template_name = "selective_transfer/selective_transfer_job_detail.html"
    owner_accessor = "created_by"
