from adit.main.models import TransferTask
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic.edit import CreateView
from django.views.generic import DetailView
from django.http import HttpResponseBadRequest
from rest_framework import generics, permissions
from adit.main.mixins import OwnerRequiredMixin
from .forms import SelectiveTransferJobForm
from .models import SelectiveTransferJob


class SelectiveTransferJobFormView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    """A view class to render the selective transfer form.

    POST (and the creation of the job) is not handled by this view because the
    job itself is created by using the REST API and an AJAX call.
    """

    template_name = "selective_transfer/selective_transfer_job_form.html"
    form_class = SelectiveTransferJobForm
    permission_required = "selective_transfer.add_selectivetransferjob"

    def form_valid(self, form):
        if self.request.POST.get("action") == "query":
            data = form.cleaned_data
            server = form.instance.source.dicomserver
            connector = server.create_connector()
            studies = connector.find_studies(
                patient_id=data["patient_id"],
                patient_name=data["patient_name"],
                birth_date=data["patient_birth_date"],
                accession_number=data["accession_number"],
                study_date=data["study_date"],
                modality=data["modality"],
                limit_results=50,
            )
            return self.render_to_response(
                self.get_context_data(
                    query=True,
                    query_results=studies,
                )
            )
        else:
            user = self.request.user
            selected_studies = self.request.POST.getlist("selected_studies")
            error = None
            if not selected_studies:
                error = "At least one study must be selected for transfer."
            elif len(selected_studies) > 10 and not user.is_staff:
                error = "Maximum 10 studies per transfer can be selected."

            if error:
                return self.render_to_response(
                    self.get_context_data(transfer=True, error=error)
                )
            else:
                form.instance.owner = user
                self.object = form.save()

                pseudonym = form.cleaned_data["pseudonym"]
                for selected_study in selected_studies:
                    study_data = selected_study.split("\\")
                    patient_id = study_data[0]
                    study_uid = study_data[1]
                    TransferTask.objects.create(
                        job=self.object,
                        patient_id=patient_id,
                        study_uid=study_uid,
                        pseudonym=pseudonym,
                    )

                return self.render_to_response(self.get_context_data(transfer=True))


class SelectiveTransferJobDetailView(
    LoginRequiredMixin, OwnerRequiredMixin, DetailView
):
    model = SelectiveTransferJob
    context_object_name = "job"
    template_name = "selective_transfer/selective_transfer_job_detail.html"
    owner_accessor = "owner"
