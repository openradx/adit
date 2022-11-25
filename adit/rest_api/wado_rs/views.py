import os
from rest_framework.exceptions import NotFound
from django.conf import settings

from ..views import DicomWebAPIView
from .models import (
    DicomWadoJob,
    DicomWadoTask,
)
from ..renderers import (
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
    FOLDER_ADIT = "adit/rest_api/wado_rs/tmp"


class RetrieveStudyAPIView(RetrieveAPIView):
    LEVEL = "STUDY"

    def get(self, request, *args, **kwargs):
        SourceServer, study_uid, series_uid = self.handle_request(
            request, "WADO-RS", *args, **kwargs
        )

        mode, content_type, boundary = self.handle_accept_header(
            request, *args, **kwargs
        )
        folder_path, file_path = self.generate_temp_files(
            study_uid,
            series_uid,
            self.LEVEL,
        )

        job = DicomWadoJob(
            source=SourceServer,
            owner=request.user,
            status=DicomWadoJob.Status.PENDING,
            folder_path=folder_path,
            file_path=file_path,
            mode=mode,
            content_type=content_type,
            boundary=boundary,
        )
        job.save()

        task = DicomWadoTask(
            study_uid=study_uid,
            series_uid=series_uid,
            job=job,
            task_id=0,
        )
        task.save()

        job.delay()

        while task.status != "SU":
            if task.status == "FA":
                raise NotFound(
                    "Retrieving the dicom object failed. Please make sure the object exists."
                )
            task.refresh_from_db()

        response = request.accepted_renderer.create_response(
            file_path=file_path, type=content_type, boundary=boundary
        )
        os.remove(file_path)
        os.rmdir(folder_path/"dicom_files")
        os.rmdir(folder_path)

        return response


class RetrieveSeriesAPIView(RetrieveAPIView):
    LEVEL = "SERIES"

    def get(self, request, *args, **kwargs):
        SourceServer, study_uid, series_uid = self.handle_request(
            request, "WADO-RS", *args, **kwargs
        )
        mode, content_type, boundary = self.handle_accept_header(
            request, *args, **kwargs
        )
        folder_path, file_path = self.generate_temp_files(
            study_uid,
            series_uid,
            self.LEVEL,
        )

        job = DicomWadoJob(
            source=SourceServer,
            owner=request.user,
            status=DicomWadoJob.Status.PENDING,
            folder_path=folder_path,
            file_path=file_path,
            mode=mode,
            content_type=content_type,
            boundary=boundary,
            urgent=True,
        )
        job.save()

        task = DicomWadoTask(
            study_uid=study_uid,
            series_uid=series_uid,
            job=job,
            task_id=0,
        )
        task.save()

        job.delay()

        while task.status != "SU":
            if task.status == "FA":
                raise NotFound(
                    "Retrieving the dicom object failed. Please make sure the object exists."
                )
            task.refresh_from_db()

        response = request.accepted_renderer.create_response(
            file_path=file_path, type=content_type, boundary=boundary
        )
        os.remove(file_path)
        os.rmdir(folder_path)

        return response
