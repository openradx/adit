from typing import Any, Dict
from django.views.generic import View
from django.views.generic.edit import DeleteView, CreateView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    UserPassesTestMixin,
    PermissionRequiredMixin,
)
from django.urls import re_path
from django.shortcuts import redirect
from django.core.exceptions import SuspiciousOperation
from django.contrib import messages
from django.db.models.query import QuerySet
from django.conf import settings
from django_tables2 import SingleTableMixin
from django_filters.views import FilterView
from revproxy.views import ProxyView
from .models import DicomJob
from .mixins import OwnerRequiredMixin, PageSizeSelectMixin


class DicomJobListView(  # pylint: disable=too-many-ancestors
    LoginRequiredMixin, SingleTableMixin, PageSizeSelectMixin, FilterView
):
    model = None
    table_class = None
    filterset_class = None
    template_name = None

    def get_queryset(self) -> QuerySet:
        return self.model.objects.select_related("source").filter(
            owner=self.request.user
        )


class TransferJobListView(DicomJobListView):  # pylint: disable=too-many-ancestors
    def get_queryset(self) -> QuerySet:
        return self.model.objects.select_related("source", "destination").filter(
            owner=self.request.user
        )


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
    owner_accessor = "owner"
    success_message = "Job with ID %(id)d was deleted successfully"

    def delete(self, request, *args, **kwargs):
        job = self.get_object()
        if not job.is_deletable:
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} is not deletable."
            )

        # As SuccessMessageMixin does not work in DeleteView we have to do
        # it manually (https://code.djangoproject.com/ticket/21936)
        messages.success(request, self.success_message % job.__dict__)
        return super().delete(request, *args, **kwargs)


class DicomJobCancelView(
    LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View
):
    model = None
    owner_accessor = "owner"
    success_message = "Job with ID %(id)d was canceled"

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        job = self.get_object()
        if not job.is_cancelable:
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} is not cancelable."
            )

        job.status = DicomJob.Status.CANCELING
        job.save()
        messages.success(request, self.success_message % job.__dict__)
        return redirect(job)


class DicomJobVerifyView(
    LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View
):
    model = None
    owner_accessor = "owner"
    success_message = "Job with ID %(id)d was verified"

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
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


class DicomTaskDetailView(LoginRequiredMixin, OwnerRequiredMixin, DetailView):
    model = None
    job_url_name = None
    template_name = None
    context_object_name = "task"
    owner_accessor = "owner"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["job_url_name"] = self.job_url_name
        return context


class FlowerProxyView(UserPassesTestMixin, ProxyView):
    """A reverse proxy view to access the Flower Celery admin tool.

    By using a reverse proxy we can use the Django authentication
    to check for an logged in admin user.
    Code from https://stackoverflow.com/a/61997024/166229
    """

    upstream = "http://{}:{}".format(settings.FLOWER_HOST, settings.FLOWER_PORT)
    url_prefix = "flower"
    rewrite = ((r"^/{}$".format(url_prefix), r"/{}/".format(url_prefix)),)

    def test_func(self):
        return self.request.user.is_staff

    @classmethod
    def as_url(cls):
        return re_path(r"^(?P<path>{}.*)$".format(cls.url_prefix), cls.as_view())
