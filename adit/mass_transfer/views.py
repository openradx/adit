import csv
from typing import Any, cast

from adit_radis_shared.common.mixins import PageSizeSelectMixin, RelatedFilterMixin
from adit_radis_shared.common.views import BaseUpdatePreferencesView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django_tables2 import SingleTableMixin

from adit.core.views import (
    DicomJobCancelView,
    DicomJobCreateView,
    DicomJobDeleteView,
    DicomJobDetailView,
    DicomJobRestartView,
    DicomJobResumeView,
    DicomJobRetryView,
    DicomJobVerifyView,
    DicomTaskDeleteView,
    DicomTaskDetailView,
    DicomTaskForceRetryView,
    DicomTaskKillView,
    DicomTaskResetView,
    TransferJobListView,
)

from .filters import MassTransferJobFilter, MassTransferTaskFilter, MassTransferVolumeFilter
from .forms import MassTransferJobForm
from .mixins import MassTransferLockedMixin
from .models import (
    MassTransferJob,
    MassTransferTask,
    MassTransferVolume,
)
from .tables import MassTransferJobTable, MassTransferTaskTable, MassTransferVolumeTable

MASS_TRANSFER_SOURCE = "mass_transfer_source"
MASS_TRANSFER_DESTINATION = "mass_transfer_destination"
MASS_TRANSFER_GRANULARITY = "mass_transfer_granularity"
MASS_TRANSFER_SEND_FINISHED_MAIL = "mass_transfer_send_finished_mail"


class MassTransferUpdatePreferencesView(MassTransferLockedMixin, BaseUpdatePreferencesView):
    allowed_keys = [
        MASS_TRANSFER_SOURCE,
        MASS_TRANSFER_DESTINATION,
        MASS_TRANSFER_GRANULARITY,
        MASS_TRANSFER_SEND_FINISHED_MAIL,
    ]


class MassTransferJobListView(MassTransferLockedMixin, TransferJobListView):
    model = MassTransferJob
    table_class = MassTransferJobTable
    filterset_class = MassTransferJobFilter
    template_name = "mass_transfer/mass_transfer_job_list.html"


class MassTransferJobCreateView(MassTransferLockedMixin, DicomJobCreateView):
    model = MassTransferJob
    form_class = MassTransferJobForm
    template_name = "mass_transfer/mass_transfer_job_form.html"
    permission_required = "mass_transfer.add_masstransferjob"
    object: MassTransferJob

    def get_initial(self) -> dict[str, Any]:
        initial = super().get_initial()
        preferences: dict[str, Any] = self.request.user.preferences

        source = preferences.get(MASS_TRANSFER_SOURCE)
        if source is not None:
            initial["source"] = source

        destination = preferences.get(MASS_TRANSFER_DESTINATION)
        if destination is not None:
            initial["destination"] = destination

        granularity = preferences.get(MASS_TRANSFER_GRANULARITY)
        if granularity is not None:
            initial["partition_granularity"] = granularity

        send_finished_mail = preferences.get(MASS_TRANSFER_SEND_FINISHED_MAIL)
        if send_finished_mail is not None:
            initial["send_finished_mail"] = send_finished_mail

        return initial

    def form_valid(self, form):
        return super().form_valid(form, settings.START_MASS_TRANSFER_UNVERIFIED)


class MassTransferJobDetailView(MassTransferLockedMixin, DicomJobDetailView):
    table_class = MassTransferTaskTable
    filterset_class = MassTransferTaskFilter
    model = MassTransferJob
    context_object_name = "job"
    template_name = "mass_transfer/mass_transfer_job_detail.html"


class MassTransferJobCsvExportView(LoginRequiredMixin, MassTransferLockedMixin, View):
    """Streams a full CSV export of all volumes for a mass transfer job."""

    COLUMNS = [
        "partition_key",
        "pseudonym",
        "patient_id",
        "accession_number",
        "study_instance_uid",
        "study_instance_uid_pseudonymized",
        "series_instance_uid",
        "series_instance_uid_pseudonymized",
        "modality",
        "study_description",
        "series_description",
        "series_number",
        "study_datetime",
        "institution_name",
        "number_of_images",
    ]

    def get(self, request, pk):
        if request.user.is_staff:
            qs = MassTransferJob.objects.all()
        else:
            qs = MassTransferJob.objects.filter(owner=request.user)

        job = get_object_or_404(qs, pk=pk)

        volumes = MassTransferVolume.objects.filter(job=job).values_list(*self.COLUMNS)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="mass_transfer_job_{job.pk}.csv"'

        writer = csv.writer(response)
        if job.pseudonym_salt:
            response.write(f"# Pseudonym salt: {job.pseudonym_salt}\n")
        writer.writerow(self.COLUMNS)
        for row in volumes.iterator():
            writer.writerow(row)

        return response


class MassTransferJobDeleteView(MassTransferLockedMixin, DicomJobDeleteView):
    model = MassTransferJob
    success_url = cast(str, reverse_lazy("mass_transfer_job_list"))


class MassTransferJobVerifyView(MassTransferLockedMixin, DicomJobVerifyView):
    model = MassTransferJob


class MassTransferJobCancelView(MassTransferLockedMixin, DicomJobCancelView):
    model = MassTransferJob


class MassTransferJobResumeView(MassTransferLockedMixin, DicomJobResumeView):
    model = MassTransferJob


class MassTransferJobRetryView(MassTransferLockedMixin, DicomJobRetryView):
    model = MassTransferJob


class MassTransferJobRestartView(MassTransferLockedMixin, DicomJobRestartView):
    model = MassTransferJob


class MassTransferTaskDetailView(
    MassTransferLockedMixin,
    SingleTableMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
    DicomTaskDetailView,
):
    model = MassTransferTask
    job_url_name = "mass_transfer_job_detail"
    template_name = "mass_transfer/mass_transfer_task_detail.html"
    table_class = MassTransferVolumeTable
    filterset_class = MassTransferVolumeFilter
    table_pagination = {"per_page": 25}

    def get_filter_queryset(self) -> QuerySet[MassTransferVolume]:
        task = cast(MassTransferTask, self.get_object())
        return task.volumes


class MassTransferTaskDeleteView(MassTransferLockedMixin, DicomTaskDeleteView):
    model = MassTransferTask


class MassTransferTaskResetView(MassTransferLockedMixin, DicomTaskResetView):
    model = MassTransferTask


class MassTransferTaskForceRetryView(MassTransferLockedMixin, DicomTaskForceRetryView):
    model = MassTransferTask


class MassTransferTaskKillView(MassTransferLockedMixin, DicomTaskKillView):
    model = MassTransferTask


