from typing import Any, Dict, Optional
from django.shortcuts import render
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.views.generic import View
from django.views.generic.base import TemplateView
from django.views.generic.edit import DeleteView, CreateView, FormView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    UserPassesTestMixin,
    PermissionRequiredMixin,
)
from django.urls import re_path, reverse_lazy
from django.shortcuts import redirect
from django.core.exceptions import SuspiciousOperation
from django.conf import settings
from django.http.response import Http404
from django.db import models
from django.db.models.query import QuerySet
from django_tables2 import SingleTableMixin
from django_filters.views import FilterView
from revproxy.views import ProxyView

from adit.core.tasks import broadcast_mail
from ..celery import app as celery_app
from .site import job_stats_collectors
from .models import CoreSettings, DicomJob, DicomTask
from .mixins import OwnerRequiredMixin, PageSizeSelectMixin
from .forms import BroadcastForm


@staff_member_required
def sandbox(request):
    messages.add_message(request, messages.SUCCESS, "This message is server generated!")
    return render(request, "core/sandbox.html", {})


@staff_member_required
def admin_section(request):
    status_list = DicomJob.Status.choices
    job_stats = [collector() for collector in job_stats_collectors]
    return render(
        request,
        "core/admin_section.html",
        {
            "status_list": status_list,
            "job_stats": job_stats,
        },
    )


class BroadcastView(UserPassesTestMixin, FormView):
    template_name = "core/broadcast.html"
    form_class = BroadcastForm
    success_url = reverse_lazy("broadcast")

    def test_func(self):
        return self.request.user.is_staff

    def form_valid(self, form):
        subject = form.cleaned_data["subject"]
        message = form.cleaned_data["message"]

        broadcast_mail.delay(subject, message)

        messages.add_message(
            self.request,
            messages.SUCCESS,
            "Mail queued for sending successfully",
        )

        return super().form_valid(form)


class HomeView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        core_settings = CoreSettings.get()
        context["announcement"] = core_settings.announcement
        return context


class DicomJobListView(
    LoginRequiredMixin, SingleTableMixin, PageSizeSelectMixin, FilterView
):
    model = None
    table_class = None
    filterset_class = None
    template_name = None

    def get_queryset(self) -> QuerySet:
        if self.request.user.is_staff and self.request.GET.get("all"):
            queryset = self.model.objects.all()
        else:
            queryset = self.model.objects.filter(owner=self.request.user)

        return queryset.select_related("source")

    def get_table_kwargs(self):
        kwargs = super().get_table_kwargs()

        if not (self.request.user.is_staff and self.request.GET.get("all")):
            kwargs["exclude"] = ("owner",)

        return kwargs


class TransferJobListView(DicomJobListView):  # pylint: disable=too-many-ancestors
    def get_queryset(self) -> QuerySet:
        return super().get_queryset().select_related("destination")


class DicomJobCreateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    CreateView,
):
    model = None
    form_class = None
    template_name = None
    permission_required = None

    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


class DicomJobDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = None
    success_url = None
    success_message = "Job with ID %(id)d was deleted successfully"

    def delete(self, request, *args, **kwargs):
        job = self.get_object()
        if not job.is_deletable:
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} is not deletable."
            )

        for dicom_task in job.tasks.all():
            if dicom_task.celery_task_id:
                celery_app.control.revoke(dicom_task.celery_task_id)

        # As SuccessMessageMixin does not work in DeleteView we have to do
        # it manually (https://code.djangoproject.com/ticket/21936)
        messages.success(request, self.success_message % job.__dict__)
        return super().delete(request, *args, **kwargs)


class DicomJobVerifyView(
    LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View
):
    model = None
    success_message = "Job with ID %(id)d was verified"

    def post(self, request, *args, **kwargs):
        job = self.get_object()
        if job.is_verified:
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} was already verified."
            )

        job.status = DicomJob.Status.PENDING
        job.save()

        job.delay()

        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomJobCancelView(
    LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View
):
    model = None
    success_message = "Job with ID %(id)d was canceled"

    def post(self, request, *args, **kwargs):
        job = self.get_object()
        if not job.is_cancelable:
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} is not cancelable."
            )

        for dicom_task in job.tasks.filter(status=DicomTask.Status.PENDING):
            if dicom_task.celery_task_id:
                celery_app.control.revoke(dicom_task.celery_task_id)
            dicom_task.status = DicomTask.Status.CANCELED
            dicom_task.save()

        tasks_in_progress_count = job.tasks.filter(
            status=DicomTask.Status.IN_PROGRESS
        ).count()

        # If there is a still in progress task then the job will be set to canceled when
        # the processing of the task is finished (see core.tasks.HandleFinishedDicomJob)
        if tasks_in_progress_count > 0:
            job.status = DicomJob.Status.CANCELING
        else:
            job.status = DicomJob.Status.CANCELED

        job.save()

        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomJobResumeView(
    LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View
):
    model = None
    success_message = "Job with ID %(id)d will be resumed"

    def post(self, request, *args, **kwargs):
        job = self.get_object()
        if not job.is_resumable:
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} is not resumable."
            )

        for task in job.tasks.filter(status=DicomTask.Status.CANCELED):
            task.status = DicomTask.Status.PENDING
            task.save()

        job.status = DicomJob.Status.PENDING
        job.save()

        job.delay()

        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomJobRetryView(
    LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View
):
    model = None
    success_message = "Job with ID %(id)d will be retried"

    def post(self, request, *args, **kwargs):
        job = self.get_object()
        if not job.is_retriable:
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} is not retriable."
            )

        for task in job.tasks.filter(status=DicomTask.Status.FAILURE):
            task.status = DicomTask.Status.PENDING
            task.retries = 0
            task.message = ""
            task.log = ""
            task.start = None
            task.end = None
            task.save()

        job.status = DicomJob.Status.PENDING
        job.save()

        job.delay()

        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomJobRestartView(
    LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View
):
    model = None
    success_message = "Job with ID %(id)d will be restarted"

    def post(self, request, *args, **kwargs):
        job = self.get_object()
        if not request.user.is_staff or not job.is_restartable:
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} is not restartable."
            )

        for task in job.tasks.all():
            task.status = DicomTask.Status.PENDING
            task.retries = 0
            task.message = ""
            task.log = ""
            task.start = None
            task.end = None
            task.save()

        job.status = DicomJob.Status.PENDING
        job.save()

        job.delay()

        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomTaskDetailView(LoginRequiredMixin, OwnerRequiredMixin, DetailView):
    model = None
    job_url_name = None
    template_name = None
    context_object_name = "task"
    owner_accessor = "job.owner"

    def get_object(
        self, queryset: Optional[models.query.QuerySet] = None
    ) -> models.Model:
        if queryset is None:
            queryset = self.get_queryset()

        job_id = self.kwargs.get("job_id")
        task_id = self.kwargs.get("task_id")

        if job_id is None or task_id is None:
            raise AttributeError(
                f"Dicom task detail view {self.__class__.__name__} must "
                "be called with a job_id and a task_id in the URLconf."
            )

        queryset = queryset.filter(job_id=job_id, task_id=task_id)

        try:
            obj = queryset.get()
        except queryset.model.DoesNotExist as err:
            raise Http404(
                f"No {queryset.model._meta.verbose_name} found matching the query"
            ) from err
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["job_url_name"] = self.job_url_name
        return context


class AdminProxyView(UserPassesTestMixin, ProxyView):
    """A reverse proxy view to hide other services behind that only an admin can access.

    By using a reverse proxy we can use the Django authentication
    to check for an logged in admin user.
    Code from https://stackoverflow.com/a/61997024/166229
    """

    def test_func(self):
        return self.request.user.is_staff

    @classmethod
    def as_url(cls):
        return re_path(rf"^{cls.url_prefix}/(?P<path>.*)$", cls.as_view())


class RabbitManagementProxyView(AdminProxyView):
    upstream = (
        f"http://{settings.RABBIT_MANAGEMENT_HOST}:{settings.RABBIT_MANAGEMENT_PORT}"
    )
    url_prefix = "rabbit"
    rewrite = ((rf"^/{url_prefix}$", r"/"),)


class FlowerProxyView(AdminProxyView):
    upstream = f"http://{settings.FLOWER_HOST}:{settings.FLOWER_PORT}"
    url_prefix = "flower"
    rewrite = ((rf"^/{url_prefix}$", rf"/{url_prefix}/"),)

    @classmethod
    def as_url(cls):
        # Flower needs a bit different setup then the other proxy views as flower
        # uses a prefix itself (see docker compose service)
        return re_path(rf"^(?P<path>{cls.url_prefix}.*)$", cls.as_view())


class Orthanc1ProxyView(AdminProxyView):
    upstream = f"http://{settings.ORTHANC1_HOST}:{settings.ORTHANC1_HTTP_PORT}"
    url_prefix = "orthanc1"
    rewrite = ((rf"^/{url_prefix}$", r"/"),)


class Orthanc2ProxyView(AdminProxyView):
    upstream = f"http://{settings.ORTHANC2_HOST}:{settings.ORTHANC2_HTTP_PORT}"
    url_prefix = "orthanc2"
    rewrite = ((rf"^/{url_prefix}$", r"/"),)
