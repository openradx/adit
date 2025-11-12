from typing import Any, cast

from adit_radis_shared.common.mixins import PageSizeSelectMixin, RelatedFilterMixin
from adit_radis_shared.common.site import THEME_PREFERENCE_KEY
from adit_radis_shared.common.types import AuthenticatedHttpRequest
from adit_radis_shared.common.views import (
    AdminProxyView,
    BaseHomeView,
    BaseUpdatePreferencesView,
)
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.core.exceptions import SuspiciousOperation
from django.db.models.query import QuerySet
from django.forms import ModelForm
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import View
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, DeleteView
from django_filters import FilterSet
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin
from django_tables2.tables import Table
from procrastinate.contrib.django import app

from adit.core.utils.model_utils import reset_tasks

from .models import DicomJob, DicomTask
from .site import job_stats_collectors


def health(request) -> JsonResponse:
    """Return a simple response so external systems can verify the service is up."""

    return JsonResponse({"status": "ok"})


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


class HomeView(BaseHomeView):
    template_name = "core/home.html"


class UpdatePreferencesView(BaseUpdatePreferencesView):
    allowed_keys = [THEME_PREFERENCE_KEY]


class DicomJobListView(LoginRequiredMixin, SingleTableMixin, PageSizeSelectMixin, FilterView):
    model: type[DicomJob]
    table_class: type[Table]
    filterset_class: type[FilterSet]
    template_name: str
    request: AuthenticatedHttpRequest

    def get_queryset(self) -> QuerySet:
        if self.request.user.is_staff and self.request.GET.get("all"):
            return self.model.objects.all().order_by("-created")

        return self.model.objects.filter(owner=self.request.user).order_by("-created")

    def get_table_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_table_kwargs()

        if not (self.request.user.is_staff and self.request.GET.get("all")):
            kwargs["exclude"] = ("owner",)

        return kwargs


class TransferJobListView(DicomJobListView):
    pass


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
    object: DicomJob

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form: ModelForm, transfer_unverified: bool) -> HttpResponse:
        user = self.request.user
        form.instance.owner = user
        response = super().form_valid(form)

        job = self.object  # set by super().form_valid(form)
        if user.is_staff or transfer_unverified:
            job.status = DicomJob.Status.PENDING
            job.save()

            job.queue_pending_tasks()

        return response


class DicomJobDetailView(
    LoginRequiredMixin,
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
    request: AuthenticatedHttpRequest

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.model.objects.all()
        return self.model.objects.filter(owner=self.request.user)

    def get_filter_queryset(self) -> QuerySet[DicomTask]:
        job = cast(DicomJob, self.get_object())
        return job.tasks


class DicomJobDeleteView(LoginRequiredMixin, DeleteView):
    model: type[DicomJob]
    success_url: str
    success_message = "Job with ID %(id)d was deleted"
    request: AuthenticatedHttpRequest
    object: DicomJob

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.model.objects.all()
        return self.model.objects.filter(owner=self.request.user)

    def form_valid(self, form: ModelForm) -> HttpResponse:
        job = cast(DicomJob, self.get_object())

        if not job.is_deletable:
            raise SuspiciousOperation(
                f"Job with ID {job.pk} and status {job.get_status_display()} is not deletable."
            )

        # We have to create the success message before we delete the job
        # as the ID afterwards will be None
        success_message = self.success_message % job.__dict__

        for task in job.tasks.all():
            if task.queued_job_id is not None:
                app.job_manager.cancel_job_by_id(task.queued_job_id, delete_job=True)

        job.delete()

        messages.success(self.request, success_message)
        return redirect(self.get_success_url())


class DicomJobVerifyView(LoginRequiredMixin, UserPassesTestMixin, SingleObjectMixin, View):
    model: type[DicomJob]
    success_message = "Job with ID %(id)d was verified"
    request: AuthenticatedHttpRequest

    def test_func(self) -> bool:
        return self.request.user.is_staff

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.model.objects.all()
        return self.model.objects.filter(owner=self.request.user)

    def post(self, request: AuthenticatedHttpRequest, *args, **kwargs) -> HttpResponse:
        job = cast(DicomJob, self.get_object())
        if job.is_verified:
            raise SuspiciousOperation(
                f"Job with ID {job.pk} and status {job.get_status_display()} was already verified."
            )

        job.status = DicomJob.Status.PENDING
        job.save()

        job.queue_pending_tasks()

        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomJobCancelView(LoginRequiredMixin, SingleObjectMixin, View):
    model: type[DicomJob]
    success_message = "Job with ID %(id)d was canceled"
    request: AuthenticatedHttpRequest

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.model.objects.all()
        return self.model.objects.filter(owner=self.request.user)

    def post(self, request: AuthenticatedHttpRequest, *args, **kwargs) -> HttpResponse:
        job = cast(DicomJob, self.get_object())
        if not job.is_cancelable:
            raise SuspiciousOperation(
                f"Job with ID {job.pk} and status {job.get_status_display()} is not cancelable."
            )

        tasks = job.tasks.filter(status=DicomTask.Status.PENDING)
        for dicom_task in tasks:
            queued_job_id = dicom_task.queued_job_id
            if queued_job_id is not None:
                app.job_manager.cancel_job_by_id(queued_job_id, delete_job=True)
        tasks.update(status=DicomTask.Status.CANCELED)

        if job.tasks.filter(status=DicomTask.Status.IN_PROGRESS).exists():
            job.status = DicomJob.Status.CANCELING
        else:
            job.status = DicomJob.Status.CANCELED
        job.save()

        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomJobResumeView(LoginRequiredMixin, SingleObjectMixin, View):
    model: type[DicomJob]
    success_message = "Job with ID %(id)d will be resumed"
    request: AuthenticatedHttpRequest

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.model.objects.all()
        return self.model.objects.filter(owner=self.request.user)

    def post(self, request: AuthenticatedHttpRequest, *args, **kwargs) -> HttpResponse:
        job = cast(DicomJob, self.get_object())
        if not job.is_resumable:
            raise SuspiciousOperation(
                f"Job with ID {job.pk} and status {job.get_status_display()} is not resumable."
            )

        job.tasks.filter(status=DicomTask.Status.CANCELED).update(status=DicomTask.Status.PENDING)

        job.status = DicomJob.Status.PENDING
        job.save()

        job.queue_pending_tasks()

        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomJobRetryView(LoginRequiredMixin, SingleObjectMixin, View):
    model: type[DicomJob]
    success_message = "Job with ID %(id)d will be retried"
    request: AuthenticatedHttpRequest

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.model.objects.all()
        return self.model.objects.filter(owner=self.request.user)

    def post(self, request: AuthenticatedHttpRequest, *args, **kwargs) -> HttpResponse:
        job = cast(DicomJob, self.get_object())
        if not job.is_retriable:
            raise SuspiciousOperation(
                f"Job with ID {job.pk} and status {job.get_status_display()} is not retriable."
            )

        job.reset_tasks(only_failed=True)

        job.status = DicomJob.Status.PENDING
        job.save()

        job.queue_pending_tasks()

        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomJobRestartView(LoginRequiredMixin, UserPassesTestMixin, SingleObjectMixin, View):
    model: type[DicomJob]
    success_message = "Job with ID %(id)d will be restarted"
    request: AuthenticatedHttpRequest

    def test_func(self) -> bool:
        return self.request.user.is_staff

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.model.objects.all()
        return self.model.objects.filter(owner=self.request.user)

    def post(self, request: AuthenticatedHttpRequest, *args, **kwargs) -> HttpResponse:
        job = cast(DicomJob, self.get_object())
        if not request.user.is_staff or not job.is_restartable:
            raise SuspiciousOperation(
                f"Job with ID {job.pk} and status {job.get_status_display()} is not restartable."
            )

        job.reset_tasks()

        job.status = DicomJob.Status.PENDING
        job.message = ""
        job.save()

        job.queue_pending_tasks()

        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomTaskDetailView(LoginRequiredMixin, DetailView):
    model: type[DicomTask]
    job_url_name: str
    template_name: str
    context_object_name = "task"
    request: AuthenticatedHttpRequest

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.model.objects.all()
        return self.model.objects.filter(job__owner=self.request.user)

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["job_url_name"] = self.job_url_name
        return context


class DicomTaskDeleteView(LoginRequiredMixin, DeleteView):
    model: type[DicomTask]
    success_message = "Task with ID %(id)d was deleted"
    request: AuthenticatedHttpRequest

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.model.objects.all()
        return self.model.objects.filter(job__owner=self.request.user)

    def form_valid(self, form: ModelForm) -> HttpResponse:
        task = cast(DicomTask, self.get_object())

        if not task.is_deletable:
            raise SuspiciousOperation(
                f"Task with ID {task.pk} and status {task.get_status_display()} is not deletable."
            )

        # We have to create the success message before we delete the task
        # as the ID afterwards will be None
        success_message = self.success_message % task.__dict__

        task.delete()
        task.job.post_process()

        messages.success(self.request, success_message)
        return redirect(task.job)


class DicomTaskResetView(LoginRequiredMixin, SingleObjectMixin, View):
    model: type[DicomTask]
    success_message = "Task with ID %(id)d was reset"
    request: AuthenticatedHttpRequest

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.model.objects.all()
        return self.model.objects.filter(job__owner=self.request.user)

    def post(self, request: AuthenticatedHttpRequest, *args, **kwargs) -> HttpResponse:
        task = cast(DicomTask, self.get_object())
        if not task.is_resettable:
            raise SuspiciousOperation(
                f"Task with ID {task.pk} and status {task.get_status_display()} is not resettable."
            )

        reset_tasks(self.model.objects.filter(pk=task.pk))
        ## Refresh the task object from database to get the updated status
        task.refresh_from_db()
        task.queue_pending_task()
        task.job.post_process()

        messages.success(request, self.success_message % task.__dict__)
        return redirect(task)


class DicomTaskKillView(LoginRequiredMixin, UserPassesTestMixin, SingleObjectMixin, View):
    model: type[DicomTask]
    success_message = "Task with ID %(id)d will be killed"
    request: AuthenticatedHttpRequest

    def test_func(self) -> bool:
        return self.request.user.is_staff

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.model.objects.all()
        return self.model.objects.filter(owner=self.request.user)

    def post(self, request: AuthenticatedHttpRequest, *args, **kwargs) -> HttpResponse:
        task = cast(DicomTask, self.get_object())
        if not task.is_killable:
            raise SuspiciousOperation(
                f"Task with ID {task.pk} and status {task.get_status_display()} is not killable."
            )

        queued_job_id = task.queued_job_id
        if queued_job_id is not None:
            app.job_manager.cancel_job_by_id(queued_job_id, abort=True, delete_job=True)

        messages.success(request, self.success_message % task.__dict__)
        return redirect(task)


class Orthanc1ProxyView(AdminProxyView):
    upstream = f"http://{settings.ORTHANC1_HOST}:{settings.ORTHANC1_HTTP_PORT}"  # type: ignore
    url_prefix = "orthanc1"
    rewrite = ((rf"^/{url_prefix}$", r"/"),)


class Orthanc2ProxyView(AdminProxyView):
    upstream = f"http://{settings.ORTHANC2_HOST}:{settings.ORTHANC2_HTTP_PORT}"  # type: ignore
    url_prefix = "orthanc2"
    rewrite = ((rf"^/{url_prefix}$", r"/"),)
