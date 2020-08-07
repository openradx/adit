from django.views.generic import View
from django.views.generic.edit import DeleteView
from django.views.generic.detail import SingleObjectMixin
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import re_path, reverse_lazy
from django.shortcuts import get_object_or_404
from django.core.exceptions import SuspiciousOperation
from django.contrib import messages
from django.shortcuts import redirect
from django.conf import settings
from django_tables2 import SingleTableView
from revproxy.views import ProxyView
from .models import DicomJob
from .tables import DicomJobTable
from .site import job_detail_views
from .mixins import OwnerRequiredMixin


class DicomJobListView(LoginRequiredMixin, SingleTableView):
    table_class = DicomJobTable
    template_name = "main/dicom_job_table.html"

    def get_queryset(self):
        return DicomJob.objects.filter(created_by=self.request.user)


def render_job_detail(request, pk):
    job = get_object_or_404(DicomJob, pk=pk)
    CustomDetailView = job_detail_views[job.job_type]
    return CustomDetailView.as_view()(request, pk=pk)


class DicomJobDelete(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = DicomJob
    owner_accessor = "created_by"
    success_url = reverse_lazy("dicom_job_list")
    success_message = "Job with ID %(id)s was deleted successfully"

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        # As SuccessMessageMixin does not work in DeleteView we have to do
        # it manually (https://code.djangoproject.com/ticket/21936)
        messages.success(self.request, self.success_message % obj.__dict__)
        return super().delete(request, *args, **kwargs)


class DicomJobCancel(LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View):
    model = DicomJob
    owner_accessor = "created_by"
    success_message = "Job with ID %(id)n was canceled"

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        job = self.get_object()
        if job.is_cancelable():
            job.status = DicomJob.Status.CANCELING
            job.save()
            messages.success(self.request, self.success_message % job.__dict__)
            redirect(job)
        else:
            raise SuspiciousOperation(f"Job with ID {job.id} is not cancelable.")


class FlowerProxyView(UserPassesTestMixin, ProxyView):
    """A reverse proxy view to access the Flower Celery admin tool.

    By using a reverse proxy we can check for an logged in admin user.
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
