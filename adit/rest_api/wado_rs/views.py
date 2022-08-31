import os
from django.http import HttpResponseBadRequest

from ..views import DicomWebAPIView
from .models import (
    DicomWadoJob, 
    DicomWadoTask,
) 
from ..renderers import(
    DicomJsonRenderer,
    DicomMultipartRenderer,
)
from ..formats import *


# Wado-RS
class RetrieveAPIView(DicomWebAPIView):
    MODE = "move"
    query = {
        "StudyInstanceUID": "",
        "PatientID": "",
        "SeriesInstanceUID": "",
        "SeriesDescription": "",
    }
    LEVEL = None
    renderer_classes = [DicomMultipartRenderer, DicomJsonRenderer]
    FOLDER_ADIT = "./temp_wado_rs_files"


class RetrieveStudyAPIView(RetrieveAPIView):
    LEVEL = "STUDY"
    
    def get(self, request, *args, **kwargs):
        SourceServer, study_uid, series_uid, mode, content_type, boundary \
            = self.handle_request(
                request, 
                "WADO-RS", 
                *args, 
                **kwargs
            )
        folder_path, file_path = self.generate_temp_files(
            study_uid, 
            series_uid, 
            self.LEVEL,
        )

        job = DicomWadoJob(
            source = SourceServer,
            owner = request.user,
            status = DicomWadoJob.Status.PENDING,
            folder_path = folder_path,
            file_path = file_path,
            mode = mode,
            content_type = content_type,
            boundary = boundary,
        )
        job.save()
    
        task = DicomWadoTask(
            study_uid = study_uid,
            series_uid = series_uid,
            job = job,
            task_id = 0,
        )
        task.save()

        job.delay()

        while task.status != "SU":
            if task.status=="FA":
                raise HttpResponseBadRequest("Processing the WADO-RS request failed.")
            task.refresh_from_db()

        response = request.accepted_renderer.create_response(
            file_path=file_path, 
            type=content_type, 
            boundary=boundary
        )
        os.remove(file_path)
        os.rmdir(folder_path)

        return response


class RetrieveSeriesAPIView(RetrieveAPIView):
    LEVEL = "SERIES"

    def get(self, request, *args, **kwargs):
        SourceServer, query, mode, content_type, boundary \
            = self.handle_request(request, accept_header=True, *args, **kwargs)
        folder_path, file_path = self.generate_temp_files(query, self.LEVEL)

        job = DicomWadoJob(
            source = SourceServer,
            owner = request.user,
            status = DicomWadoJob.Status.PENDING,
            folder_path = folder_path,
            file_path = file_path,
            mode = mode,
            content_type = content_type,
            boundary = boundary,
            urgent = True,
        )
        job.save()
    
        task = DicomWadoTask(
            study_uid = query.get("StudyInstanceUID"),
            series_uid = query.get("SeriesInstanceUID"),
            job = job,
            task_id = 0,
        )
        task.save()

        job.delay()

        while task.status != "SU":
            if task.status=="FA":
                raise HttpResponseBadRequest("Processing the WADO-RS request failed.")
            task.refresh_from_db()

        response = request.accepted_renderer.create_response(
            file_path=file_path, 
            type=content_type, 
            boundary=boundary
        )
        os.remove(file_path)
        os.rmdir(folder_path)

        return response