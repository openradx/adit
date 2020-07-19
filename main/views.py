from django.views.generic import DetailView, View
from django.views.generic.edit import DeleteView
from django.views.generic.detail import SingleObjectMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django_tables2 import SingleTableView
from .models import DicomJob
from .tables import DicomJobTable
from .site import job_detail_views
from .mixins import OwnerRequiredMixin

class DicomJobTable(LoginRequiredMixin, SingleTableView):
    table_class = DicomJobTable
    template_name = 'main/dicom_job_table.html'

    def get_queryset(self):
        return DicomJob.objects.filter(created_by=self.request.user)
    
def render_job_detail(request, pk):
    job = get_object_or_404(DicomJob, pk=pk)
    CustomDetailView = job_detail_views[job.job_type]
    return CustomDetailView.as_view()(request, pk=pk)

class DicomJobDelete(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = DicomJob
    owner_accessor = 'created_by'
    success_url = reverse_lazy('dicom_job_list')
    success_message = 'Job with ID %(id)s was deleted successfully'

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        # As SuccessMessageMixin does not work in DeleteView we have to do
        # it manually (https://code.djangoproject.com/ticket/21936)
        messages.success(self.request, self.success_message % obj.__dict__)
        return super().delete(request, *args, **kwargs)

class DicomJobCancel(LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View):
    model = DicomJob
    owner_accessor = 'created_by'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.is_cancelable():
            self.object.status = DicomJob.Status.CANCELING
            self.object.save()

        # TODO
