import logging
import os
from pathlib import Path

from rest_framework.exceptions import NotAcceptable, NotFound
from rest_framework.request import Request
from rest_framework.response import Response

from adit.dicom_web.views import DicomWebAPIView

from .models import DicomWadoJob, DicomWadoTask
from .renderers import ApplicationDicomJsonRenderer, MultipartApplicationDicomRenderer

logger = logging.getLogger(__name__)


class RetrieveAPIView(DicomWebAPIView):
    MODE = "move"
    query = {
        "StudyInstanceUID": "",
        "PatientID": "",
        "SeriesInstanceUID": "",
        "SeriesDescription": "",
    }
    level = None
    renderer_classes = [MultipartApplicationDicomRenderer, ApplicationDicomJsonRenderer]

    def generate_temp_files(self, study_uid: str, series_uid: str, level: str) -> Path:
        folder_path = Path(self.TMP_FOLDER)
        if level == "STUDY":
            folder_path = folder_path / ("study_" + study_uid)
            os.makedirs(folder_path, exist_ok=True)
        elif level == "SERIES":
            folder_path = folder_path / ("series_" + series_uid)
            os.makedirs(folder_path, exist_ok=True)

        return folder_path

    def check_renderer_mode(self, request: Request, mode):
        if mode != request.accepted_renderer.mode:
            raise NotAcceptable(
                f"""Media type {request.accepted_renderer.media_type} is not
                                    supported for retrieve mode {mode}"""
            )


class RetrieveStudyAPIView(RetrieveAPIView):
    level = "STUDY"

    def get(self, request, *args, **kwargs):
        self.check_renderer_mode(request, kwargs.get("mode", "bulk"))

        source_server, study_uid, series_uid = self.handle_request(
            request,
            pacs_ae_title=kwargs.get("pacs", ""),
            study_uid=kwargs.get("StudyInstanceUID", ""),
            series_uid=kwargs.get("SeriesInstanceUID", ""),
        )

        folder_path = self.generate_temp_files(study_uid, series_uid, self.level)

        job = DicomWadoJob(
            source=source_server,
            owner=request.user,
            status=DicomWadoJob.Status.PENDING,
            folder_path=folder_path,
        )
        job.save()

        task = DicomWadoTask(study_uid=study_uid, series_uid=series_uid, job=job, task_id=0)
        task.save()

        job.delay()

        while task.status != "SU":
            if task.status == "FA":
                raise NotFound(
                    "Retrieving the dicom object failed. Please make sure the object exists."
                )
            task.refresh_from_db()

        return Response(
            {"folder_path": folder_path}, content_type=request.accepted_renderer.content_type
        )


class RetrieveSeriesAPIView(RetrieveAPIView):
    level = "SERIES"

    def get(self, request, *args, **kwargs):
        self.check_renderer_mode(request, kwargs.get("mode", "bulk"))

        source_server, study_uid, series_uid = self.handle_request(
            request,
            pacs_ae_title=kwargs.get("pacs", ""),
            study_uid=kwargs.get("StudyInstanceUID", ""),
            series_uid=kwargs.get("SeriesInstanceUID", ""),
        )

        folder_path = self.generate_temp_files(study_uid, series_uid, self.level)

        job = DicomWadoJob(
            source=source_server,
            owner=request.user,
            status=DicomWadoJob.Status.PENDING,
            folder_path=folder_path,
        )
        job.save()

        task = DicomWadoTask(study_uid=study_uid, series_uid=series_uid, job=job, task_id=0)
        task.save()

        job.delay()

        while task.status != "SU":
            if task.status == "FA":
                raise NotFound(
                    "Retrieving the dicom object failed. Please make sure the object exists."
                )
            task.refresh_from_db()

        return Response(
            {"folder_path": folder_path}, content_type=request.accepted_renderer.content_type
        )
