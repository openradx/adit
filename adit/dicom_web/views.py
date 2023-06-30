import logging
import os
from pathlib import Path
from typing import Tuple

from adrf.views import APIView as AsyncApiView
from adrf.views import sync_to_async
from django.conf import settings
from rest_framework.exceptions import NotAcceptable, ParseError
from rest_framework.request import Request
from rest_framework.response import Response

from adit.core.models import DicomServer

from .renderers import (
    QidoApplicationDicomJsonRenderer,
    WadoApplicationDicomJsonRenderer,
    WadoMultipartApplicationDicomRenderer,
)
from .utils.qidors_utils import qido_find
from .utils.wadors_utils import wado_retrieve

logger = logging.getLogger(__name__)


class QueryAPIView(AsyncApiView):
    level: str
    query: dict = {
        "StudyInstanceUID": "",
        "SeriesInstanceUID": "",
        "PatientID": "",
        "PatientName": "",
        "PatientBirthDate": "",
        "PatientSex": "",
        "AccessionNumber": "",
        "StudyDate": "",
        "StudyTime": "",
        "ModalitiesInStudy": "",
        "Modality": "",
        "NumberOfStudyRelatedInstances": "",
        "NumberOfSeriesRelatedInstances": "",
        "SOPInstaceUID": "",
        "StudyDescription": "",
        "SeriesDescription": "",
        "SeriesNumber": "",
    }
    renderer_classes = [QidoApplicationDicomJsonRenderer]

    async def handle_request(self, pacs_ae_title: str) -> DicomServer:
        try:
            source_server = await DicomServer.objects.aget(ae_title=pacs_ae_title)
        except DicomServer.DoesNotExist:
            raise ParseError(f"The specified PACS with AE title: {pacs_ae_title} does not exist.")

        return source_server


class QueryStudyAPIView(QueryAPIView):
    level = "STUDY"

    async def get(
        self,
        request: Request,
        pacs: str,
    ):
        request_query = request.GET.dict()
        self.query.update(request_query)
        source_server = await self.handle_request(pacs)
        results = await qido_find(source_server, self.query, self.level)

        return Response(results)


class QuerySeriesAPIView(QueryAPIView):
    level = "SERIES"

    async def get(
        self,
        request: Request,
        pacs: str,
        study_uid: str = "",
    ):
        request_query = request.GET.dict()
        self.query.update(request_query)
        self.query["StudyInstanceUID"] = study_uid
        source_server = await self.handle_request(pacs)
        results = await qido_find(source_server, self.query, self.level)

        return Response(results)


class RetrieveAPIView(AsyncApiView):
    level: str
    TMP_FOLDER: str = settings.WADO_TMP_FOLDER
    query: dict = {
        "StudyInstanceUID": "",
        "PatientID": "",
        "SeriesInstanceUID": "",
        "SeriesDescription": "",
    }
    renderer_classes = [WadoMultipartApplicationDicomRenderer, WadoApplicationDicomJsonRenderer]

    async def handle_request(
        self, request: Request, pacs_ae_title: str, mode: str, study_uid: str, series_uid: str = ""
    ) -> Tuple[DicomServer, Path]:
        await self._check_renderer_mode(request, mode)

        try:
            source_server = await DicomServer.objects.aget(ae_title=pacs_ae_title)
        except DicomServer.DoesNotExist:
            raise ParseError(f"The specified PACS with AE title: {pacs_ae_title} does not exist.")

        folder_path = await self._generate_temp_files(study_uid, series_uid, self.level)

        return source_server, folder_path

    async def _generate_temp_files(self, study_uid: str, series_uid: str, level: str) -> Path:
        folder_path = Path(self.TMP_FOLDER)
        if level == "STUDY":
            folder_path = folder_path / ("study_" + study_uid)
            await sync_to_async(os.makedirs)(folder_path, exist_ok=True)
        elif level == "SERIES":
            folder_path = folder_path / ("series_" + series_uid)
            await sync_to_async(os.makedirs)(folder_path, exist_ok=True)

        return folder_path

    async def _check_renderer_mode(self, request: Request, mode: str):
        if mode != request.accepted_renderer.mode:  # type: ignore
            raise NotAcceptable(
                "Media type {} is not supported for retrieve mode {}".format(
                    request.accepted_renderer.media_type, mode  # type: ignore
                )
            )


class RetrieveStudyAPIView(RetrieveAPIView):
    level = "STUDY"

    async def get(
        self,
        request: Request,
        pacs: str,
        study_uid: str,
        mode: str = "bulk",
    ):
        source_server, folder_path = await self.handle_request(request, pacs, mode, study_uid)
        self.query["StudyInstanceUID"] = study_uid

        await wado_retrieve(source_server, self.query, folder_path)

        return Response(
            {"folder_path": folder_path},
            content_type=request.accepted_renderer.content_type,  # type: ignore
        )


class RetrieveSeriesAPIView(RetrieveAPIView):
    level = "SERIES"

    async def get(
        self,
        request: Request,
        pacs: str,
        study_uid: str,
        series_uid: str,
        mode: str = "bulk",
    ):
        source_server, folder_path = await self.handle_request(
            request, pacs, mode, study_uid, series_uid
        )
        self.query["StudyInstanceUID"] = study_uid
        self.query["SeriesInstanceUID"] = series_uid

        await wado_retrieve(source_server, self.query, folder_path)

        return Response(
            {"folder_path": folder_path},
            content_type=request.accepted_renderer.content_type,  # type: ignore
        )
