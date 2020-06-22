from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django_tables2 import SingleTableView
from .models import DicomJob
from .tables import DicomJobTable
from .site import job_detail_views


class DicomJobTableView(LoginRequiredMixin, SingleTableView):
    model = DicomJob
    table_class = DicomJobTable
    template_name = 'main/dicom_job_table.html'

    # def get_queryset(self, *args, **kwargs):
    #     if self.kwargs:
    #         owner = self.request.user
    #         return DicomJob.objects.filter(
    #             created_by=owner,
    #             status=self.kwargs['status']
    #         ).order_by('-created_at')
    #     else:
    #         return DicomJob.objects.all().order_by('-created_at')


class BaseJobDetail(DetailView):
    context_object_name = 'job'
    job = None
    
    def get_object(self):
        return self.job


def render_job_detail(request, pk):
    job = get_object_or_404(DicomJob, pk=pk)
    CustomDetailView = job_detail_views[job.job_type]
    return CustomDetailView.as_view(job=job)(request)
