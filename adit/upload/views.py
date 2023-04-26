from django.conf import settings
from django.shortcuts import render
from adit.core.views import (
    DicomJobCreateView
)
from adit.core.models import DicomNode, DicomFolder
from .models import UploadJob
from .forms import UploadJobForm
import os
import uuid

# Create your views here.
class UploadJobCreateView(DicomJobCreateView):
    model = UploadJob
    form_class = UploadJobForm
    template_name = "upload/upload_job_form.html"
    permission_required = "batch_transfer.add_batchtransferjob"

    def form_valid(self, form):
        user = self.request.user
        form.instance.owner = user

        upload_folder = "upload" + str(uuid.uuid1())
        job = self.object
        job.source = DicomFolder(path=upload_folder)
        
        response = super().form_valid(form)
    
        if form.is_valid():
            for f in self.request.FILES.getlist('upload_files'):
                handle_uploaded_file(f, upload_folder)

        
        if user.is_staff or settings.BATCH_TRANSFER_UNVERIFIED:
            job.status = UploadJob.Status.PENDING
            job.save()
            job.delay()

        return response

    def handle_uploaded_file(f, folder):
        directory = "/tmp/" + folder
        if not os.path.exists(directory):
            os.makedirs(directory)
        with open(directory + "/" + f.name, "wb+") as destination:
            for chunk in f.chunks():
                destination.write(chunk)