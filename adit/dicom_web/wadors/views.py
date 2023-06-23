import logging
import os
from pathlib import Path
from typing import Tuple

from rest_framework.exceptions import NotAcceptable, NotFound, ParseError
from rest_framework.request import Request
from rest_framework.response import Response

from adit.core.models import DicomServer
from adit.dicom_web.views import DicomWebAPIView

from .models import DicomWadoJob, DicomWadoTask
from .renderers import ApplicationDicomJsonRenderer, MultipartApplicationDicomRenderer

logger = logging.getLogger(__name__)


class RetrieveAPIView(DicomWebAPIView):
    query = {
        "StudyInstanceUID": "",
        "PatientID": "",
        "SeriesInstanceUID": "",
        "SeriesDescription": "",
    }
    renderer_classes = [MultipartApplicationDicomRenderer, ApplicationDicomJsonRenderer]

    def handle_request(
        self, request: Request, pacs_ae_title: str, study_uid: str, series_uid: str, mode: str
    ) -> Tuple[DicomServer, Path]:
        self._check_renderer_mode(request, mode)

        SourceServerSet = DicomServer.objects.filter(ae_title=pacs_ae_title)
        if len(SourceServerSet) < 1:
            raise ParseError(f"The specified PACS with AE title: {pacs_ae_title} does not exist.")
        SourceServer = SourceServerSet[0]

        folder_path = self._generate_temp_files(study_uid, series_uid, self.level)

        return SourceServer, folder_path

    def _generate_temp_files(self, study_uid: str, series_uid: str, level: str) -> Path:
        folder_path = Path(self.TMP_FOLDER)
        if level == "STUDY":
            folder_path = folder_path / ("study_" + study_uid)
            os.makedirs(folder_path, exist_ok=True)
        elif level == "SERIES":
            folder_path = folder_path / ("series_" + series_uid)
            os.makedirs(folder_path, exist_ok=True)

        return folder_path

    def _check_renderer_mode(self, request: Request, mode: str):
        if mode != request.accepted_renderer.mode:  # type: ignore
            raise NotAcceptable(
                "Media type {} is not supported for retrieve mode {}".format(
                    request.accepted_renderer.media_type, mode  # type: ignore
                )
            )


class RetrieveStudyAPIView(RetrieveAPIView):
    level = "STUDY"

    def get(
        self,
        request: Request,
        pacs: str,
        study_uid: str,
        series_uid: str = "",
        mode: str = "bulk",
    ):
        source_server, folder_path = self.handle_request(request, pacs, study_uid, series_uid, mode)

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
            {"folder_path": folder_path},
            content_type=request.accepted_renderer.content_type,  # type: ignore
        )


class RetrieveSeriesAPIView(RetrieveAPIView):
    level = "SERIES"

    def get(
        self,
        request: Request,
        pacs: str,
        study_uid: str,
        series_uid: str,
        mode: str = "bulk",
    ):
        source_server, folder_path = self.handle_request(request, pacs, study_uid, series_uid, mode)

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
            {"folder_path": folder_path},
            content_type=request.accepted_renderer.content_type,  # type: ignore
        )
