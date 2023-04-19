from django.shortcuts import render
from adit.core.views import (
    DicomJobCreateView
)
from .models import UploadJob
from .forms import UploadJobForm

# Create your views here.
class UploadJobCreateView(DicomJobCreateView):
    model = UploadJob
    form_class = UploadJobForm
    template_name = "upload/upload_job_form.html"
    permission_required = "batch_query.add_batchqueryjob"

    def form_valid(self, form):
        user = self.request.user
        form.instance.owner = user
        response = super().form_valid(form)

        job = self.object
        if user.is_staff or settings.BATCH_QUERY_UNVERIFIED:
            job.status = UploadJob.Status.PENDING
            job.save()
            job.delay()

        return response
