from django.shortcuts import render
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import DicomJob


class DicomJobListView(LoginRequiredMixin, ListView):
    model = DicomJob
    template_name = 'main/dicom_job_list.html'
    context_object_name = 'jobs'
    paginate_by = 25

    def get_queryset(self, *args, **kwargs):
        if self.kwargs:
            owner = self.request.user
            return DicomJob.objects.filter(
                created_by=owner,
                status=self.kwargs['status']
            ).order_by('-created_at')
        else:
            return DicomJob.objects.all().order_by('-created_at')