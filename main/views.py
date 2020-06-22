from django_tables2 import SingleTableView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import DicomJob
from .tables import DicomJobTable


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