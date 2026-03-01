import csv
from typing import Any, cast

from adit_radis_shared.common.views import BaseUpdatePreferencesView
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

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
    DicomTaskKillView,
    DicomTaskResetView,
    TransferJobListView,
)

from .filters import MassTransferJobFilter, MassTransferTaskFilter
from .forms import MassTransferFilterForm, MassTransferJobForm
from .mixins import MassTransferLockedMixin
from .models import (
    MassTransferFilter,
    MassTransferJob,
    MassTransferTask,
    MassTransferVolume,
)
from .tables import MassTransferJobTable, MassTransferTaskTable

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


class MassTransferJobAssociationsExportView(LoginRequiredMixin, MassTransferLockedMixin, View):
    """Streams a CSV of pseudonymization associations for a linking-mode job."""

    def get(self, request, pk):
        if request.user.is_staff:
            qs = MassTransferJob.objects.all()
        else:
            qs = MassTransferJob.objects.filter(owner=request.user)

        job = qs.get(pk=pk)
        volumes = (
            MassTransferVolume.objects.filter(job=job)
            .exclude(study_instance_uid_pseudonymized="")
            .order_by("study_datetime", "series_instance_uid")
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="associations_job_{job.pk}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "pseudonym",
            "patient_id",
            "study_instance_uid",
            "study_instance_uid_pseudonymized",
            "series_instance_uid",
            "series_instance_uid_pseudonymized",
        ])
        for vol in volumes.iterator():
            writer.writerow([
                vol.pseudonym,
                vol.patient_id,
                vol.study_instance_uid,
                vol.study_instance_uid_pseudonymized,
                vol.series_instance_uid,
                vol.series_instance_uid_pseudonymized,
            ])

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


class MassTransferTaskDetailView(MassTransferLockedMixin, DicomTaskDetailView):
    model = MassTransferTask
    job_url_name = "mass_transfer_job_detail"
    template_name = "mass_transfer/mass_transfer_task_detail.html"

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        task = self.object
        context["problem_volumes"] = task.volumes.filter(
            status__in=[
                MassTransferVolume.Status.ERROR,
                MassTransferVolume.Status.SKIPPED,
            ]
        ).order_by("status", "study_datetime")
        return context


class MassTransferTaskDeleteView(MassTransferLockedMixin, DicomTaskDeleteView):
    model = MassTransferTask


class MassTransferTaskResetView(MassTransferLockedMixin, DicomTaskResetView):
    model = MassTransferTask


class MassTransferTaskKillView(MassTransferLockedMixin, DicomTaskKillView):
    model = MassTransferTask


class MassTransferFilterListView(LoginRequiredMixin, MassTransferLockedMixin, ListView):
    model = MassTransferFilter
    template_name = "mass_transfer/mass_transfer_filter_list.html"
    context_object_name = "filters"

    def get_queryset(self):
        return MassTransferFilter.objects.filter(owner=self.request.user)


class MassTransferFilterCreateView(LoginRequiredMixin, MassTransferLockedMixin, CreateView):
    model = MassTransferFilter
    form_class = MassTransferFilterForm
    template_name = "mass_transfer/mass_transfer_filter_form.html"
    success_url = cast(str, reverse_lazy("mass_transfer_filter_list"))

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class MassTransferFilterUpdateView(LoginRequiredMixin, MassTransferLockedMixin, UpdateView):
    model = MassTransferFilter
    form_class = MassTransferFilterForm
    template_name = "mass_transfer/mass_transfer_filter_form.html"
    success_url = cast(str, reverse_lazy("mass_transfer_filter_list"))

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_queryset(self):
        return MassTransferFilter.objects.filter(owner=self.request.user)


class MassTransferFilterDeleteView(LoginRequiredMixin, MassTransferLockedMixin, DeleteView):
    model = MassTransferFilter
    template_name = "mass_transfer/mass_transfer_filter_confirm_delete.html"
    success_url = cast(str, reverse_lazy("mass_transfer_filter_list"))

    def get_queryset(self):
        return MassTransferFilter.objects.filter(owner=self.request.user)
