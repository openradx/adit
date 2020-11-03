from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic.edit import CreateView
from django.views.generic import DetailView
from django.http import HttpResponseBadRequest
from adit.main.mixins import OwnerRequiredMixin
from .forms import SelectiveTransferJobForm
from .models import SelectiveTransferJob
from .mixins import SelectiveTransferJobCreateMixin


class SelectiveTransferJobCreateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    SelectiveTransferJobCreateMixin,
    CreateView,
):
    """A view class to render the selective transfer form.

    POST (and the creation of the job) is not handled by this view because the
    job itself is created by using the REST API and an AJAX call.
    """

    template_name = "selective_transfer/selective_transfer_job_form.html"
    form_class = SelectiveTransferJobForm
    permission_required = "selective_transfer.add_selectivetransferjob"

    def form_valid(self, form):
        action = self.request.POST.get("action")

        if action == "query":
            studies = self.do_query(form)
            return self.render_to_response(
                self.get_context_data(query=True, query_results=studies)
            )

        if action == "transfer":
            user = self.request.user
            selected_studies = self.request.POST.getlist("selected_studies")
            try:
                job = self.do_transfer(user, form, selected_studies)
            except ValueError as err:
                return self.render_to_response(
                    self.get_context_data(transfer=True, error_message=str(err))
                )
            return self.render_to_response(
                self.get_context_data(transfer=True, created_job=job)
            )

        return HttpResponseBadRequest()


class SelectiveTransferJobDetailView(
    LoginRequiredMixin, OwnerRequiredMixin, DetailView
):
    model = SelectiveTransferJob
    context_object_name = "job"
    template_name = "selective_transfer/selective_transfer_job_detail.html"
    owner_accessor = "owner"
