from abc import ABC
from typing import Any, cast

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.core.exceptions import SuspiciousOperation
from django.db.models import Model
from django.db.models.query import QuerySet
from django.forms import Form, ModelForm
from django.http import HttpRequest, HttpResponse
from django.http.response import Http404
from django.shortcuts import redirect, render
from django.urls import re_path, reverse_lazy
from django.views.generic import View
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, DeleteView, FormView
from django_filters import FilterSet
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin
from django_tables2.tables import Table
from revproxy.views import ProxyView

from ..celery import app as celery_app
from .forms import BroadcastForm
from .mixins import OwnerRequiredMixin, PageSizeSelectMixin, RelatedFilterMixin
from .models import CoreSettings, DicomJob, DicomTask
from .site import job_stats_collectors
from .tasks import broadcast_mail
from .types import AuthenticatedHttpRequest


@staff_member_required
def sandbox(request: HttpRequest) -> HttpResponse:
    messages.add_message(request, messages.SUCCESS, "This message is server generated!")
    return render(request, "core/sandbox.html", {})


@staff_member_required
def admin_section(request: HttpRequest) -> HttpResponse:
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


class BroadcastView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = "core/broadcast.html"
    form_class = BroadcastForm
    success_url = reverse_lazy("broadcast")
    request: AuthenticatedHttpRequest

    def test_func(self) -> bool:
        return self.request.user.is_staff

    def form_valid(self, form: Form) -> HttpResponse:
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

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        core_settings = CoreSettings.get()
        assert core_settings
        context["announcement"] = core_settings.announcement
        return context


class BaseUpdateSessionView(ABC, LoginRequiredMixin, View):
    """Allows the client to update chosen session properties.

    We use this to retain some form state the user has chosen between browser
    refreshes. The implementations of this view is called by some AJAX requests
    when specific form fields are changed. (We also save the form state of those
    fields to the session when the form is submitted, see appropiate view classes, mixins
    and consumer.)
    """

    allowed_keys: list[str]

    def post(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        for key in request.POST.keys():
            if key not in self.allowed_keys:
                raise SuspiciousOperation(f"Property {key} is not allowed to be updated.")

        for key, value in request.POST.items():
            if value == "true":
                value = True
            elif value == "false":
                value = False

            request.session[key] = value

        return HttpResponse()


class DicomJobListView(LoginRequiredMixin, SingleTableMixin, PageSizeSelectMixin, FilterView):
    model: type[DicomJob]
    table_class: type[Table]
    filterset_class: type[FilterSet]
    template_name: str
    request: AuthenticatedHttpRequest

    def get_queryset(self) -> QuerySet:
        if self.request.user.is_staff and self.request.GET.get("all"):
            queryset = self.model.objects.all()
        else:
            queryset = self.model.objects.filter(owner=self.request.user)

        return queryset.select_related("source")

    def get_table_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_table_kwargs()

        if not (self.request.user.is_staff and self.request.GET.get("all")):
            kwargs["exclude"] = ("owner",)

        return kwargs


class TransferJobListView(DicomJobListView):
    def get_queryset(self) -> QuerySet:
        return super().get_queryset().select_related("destination")


class DicomJobCreateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    CreateView,
):
    model: type[DicomJob]
    form_class: type[ModelForm]
    template_name: str
    permission_required: str
    request: AuthenticatedHttpRequest

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


class DicomJobDetailView(
    LoginRequiredMixin,
    OwnerRequiredMixin,
    SingleTableMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
    DetailView,
):
    table_class: type[Table]
    filterset_class: type[FilterSet]
    model: type[DicomJob]
    context_object_name: str
    template_name: str

    def get_filter_queryset(self) -> QuerySet:
        job = cast(DicomJob, self.get_object())
        return job.tasks


class DicomJobDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model: type[DicomJob]
    success_url: str
    success_message = "Job with ID %(id)d was deleted successfully"

    def delete(self, request, *args, **kwargs) -> HttpResponse:
        job = cast(DicomJob, self.get_object())
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


class DicomJobVerifyView(LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View):
    model: type[DicomJob]
    success_message = "Job with ID %(id)d was verified"

    def post(self, request: AuthenticatedHttpRequest, *args, **kwargs) -> HttpResponse:
        job = cast(DicomJob, self.get_object())
        if job.is_verified:
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} was already verified."
            )

        job.status = DicomJob.Status.PENDING
        job.save()

        job.delay()

        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomJobCancelView(LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View):
    model: type[DicomJob]
    success_message = "Job with ID %(id)d was canceled"

    def post(self, request: AuthenticatedHttpRequest, *args, **kwargs) -> HttpResponse:
        job = cast(DicomJob, self.get_object())
        if not job.is_cancelable:
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} is not cancelable."
            )

        dicom_tasks = job.tasks.filter(status=DicomTask.Status.PENDING)
        for dicom_task in dicom_tasks.only("celery_task_id"):
            if dicom_task.celery_task_id:
                celery_app.control.revoke(dicom_task.celery_task_id)
        dicom_tasks.update(status=DicomTask.Status.CANCELED)

        tasks_in_progress_count = job.tasks.filter(status=DicomTask.Status.IN_PROGRESS).count()

        # If there is a still in progress task then the job will be set to canceled when
        # the processing of the task is finished (see tasks.ProcessDicomTask#update_job_after).
        if tasks_in_progress_count > 0:
            job.status = DicomJob.Status.CANCELING
        else:
            job.status = DicomJob.Status.CANCELED

        job.save()

        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomJobResumeView(LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View):
    model: type[DicomJob]
    success_message = "Job with ID %(id)d will be resumed"

    def post(self, request: AuthenticatedHttpRequest, *args, **kwargs) -> HttpResponse:
        job = cast(DicomJob, self.get_object())
        if not job.is_resumable:
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} is not resumable."
            )

        job.tasks.filter(status=DicomTask.Status.CANCELED).update(status=DicomTask.Status.PENDING)

        job.status = DicomJob.Status.PENDING
        job.save()

        job.delay()

        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomJobRetryView(LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View):
    model: type[DicomJob]
    success_message = "Job with ID %(id)d will be retried"

    def post(self, request: AuthenticatedHttpRequest, *args, **kwargs) -> HttpResponse:
        job = cast(DicomJob, self.get_object())
        if not job.is_retriable:
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} is not retriable."
            )

        job.reset_tasks(only_failed=True)

        job.status = DicomJob.Status.PENDING
        job.save()

        job.delay()

        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomJobRestartView(LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View):
    model: type[DicomJob]
    success_message = "Job with ID %(id)d will be restarted"

    def post(self, request: AuthenticatedHttpRequest, *args, **kwargs) -> HttpResponse:
        job = cast(DicomJob, self.get_object())
        if not request.user.is_staff or not job.is_restartable:
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} is not restartable."
            )

        job.reset_tasks()

        job.status = DicomJob.Status.PENDING
        job.save()

        job.delay()

        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomTaskDetailView(LoginRequiredMixin, OwnerRequiredMixin, DetailView):
    model: type[DicomTask]
    job_url_name: str
    template_name: str
    context_object_name = "task"
    owner_accessor = "job.owner"

    def get_object(self, queryset: QuerySet | None = None) -> Model:
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

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["job_url_name"] = self.job_url_name
        return context


class AdminProxyView(LoginRequiredMixin, UserPassesTestMixin, ProxyView):
    """A reverse proxy view to hide other services behind that only an admin can access.

    By using a reverse proxy we can use the Django authentication
    to check for an logged in admin user.
    Code from https://stackoverflow.com/a/61997024/166229
    """

    request: AuthenticatedHttpRequest

    def test_func(self):
        return self.request.user.is_staff

    @classmethod
    def as_url(cls):
        return re_path(rf"^{cls.url_prefix}/(?P<path>.*)$", cls.as_view())  # type: ignore


class RabbitManagementProxyView(AdminProxyView):
    upstream = (
        f"http://{settings.RABBIT_MANAGEMENT_HOST}:"
        f"{settings.RABBIT_MANAGEMENT_PORT}"  # type: ignore
    )
    url_prefix = "rabbit"
    rewrite = ((rf"^/{url_prefix}$", r"/"),)


class FlowerProxyView(AdminProxyView):
    upstream = f"http://{settings.FLOWER_HOST}:{settings.FLOWER_PORT}"  # type: ignore
    url_prefix = "flower"
    rewrite = ((rf"^/{url_prefix}$", rf"/{url_prefix}/"),)

    @classmethod
    def as_url(cls):
        # Flower needs a bit different setup then the other proxy views as flower
        # uses a prefix itself (see docker compose service)
        return re_path(rf"^(?P<path>{cls.url_prefix}.*)$", cls.as_view())


class Orthanc1ProxyView(AdminProxyView):
    upstream = f"http://{settings.ORTHANC1_HOST}:{settings.ORTHANC1_HTTP_PORT}"  # type: ignore
    url_prefix = "orthanc1"
    rewrite = ((rf"^/{url_prefix}$", r"/"),)


class Orthanc2ProxyView(AdminProxyView):
    upstream = f"http://{settings.ORTHANC2_HOST}:{settings.ORTHANC2_HTTP_PORT}"  # type: ignore
    url_prefix = "orthanc2"
    rewrite = ((rf"^/{url_prefix}$", r"/"),)
