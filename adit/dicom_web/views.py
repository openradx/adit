import logging
import os
from pathlib import Path
from typing import Literal

from adrf.views import APIView as AsyncApiView
from adrf.views import sync_to_async
from django.conf import settings
from rest_framework.exceptions import NotAcceptable, ParseError
from rest_framework.request import Request
from rest_framework.response import Response

from adit.core.models import DicomServer

from .parsers import StowMultipartApplicationDicomParser
from .renderers import (
    QidoApplicationDicomJsonRenderer,
    StowApplicationDicomJsonRenderer,
    WadoApplicationDicomJsonRenderer,
    WadoMultipartApplicationDicomRenderer,
)
from .utils.qidors_utils import qido_find
from .utils.stowrs_utils import stow_store
from .utils.wadors_utils import wado_retrieve

logger = logging.getLogger(__name__)


class QueryAPIView(AsyncApiView):
    level: Literal["STUDY", "SERIES"]
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
    ) -> Response:
        query: dict[str, str] = {}
        for key, value in request.GET.items():
            query[key] = value

        source_server = await self.handle_request(pacs)
        results = await qido_find(source_server, query, self.level)

        return Response([result.dataset.to_json_dict() for result in results])


class QuerySeriesAPIView(QueryAPIView):
    level = "SERIES"

    async def get(
        self,
        request: Request,
        pacs: str,
        study_uid: str = "",
    ) -> Response:
        query: dict[str, str] = {}
        for key, value in request.GET.items():
            query[key] = value

        query["StudyInstanceUID"] = study_uid
        source_server = await self.handle_request(pacs)
        results = await qido_find(source_server, query, self.level)

        return Response(results)


class RetrieveAPIView(AsyncApiView):
    level: Literal["STUDY", "SERIES"]
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
    ) -> tuple[DicomServer, Path]:
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
    ) -> Response:
        source_server, folder_path = await self.handle_request(request, pacs, mode, study_uid)
        query = self.query.copy()
        query["StudyInstanceUID"] = study_uid

        await wado_retrieve(source_server, query, folder_path)

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
    ) -> Response:
        source_server, folder_path = await self.handle_request(
            request, pacs, mode, study_uid, series_uid
        )
        query = self.query.copy()
        query["StudyInstanceUID"] = study_uid
        query["SeriesInstanceUID"] = series_uid

        await wado_retrieve(source_server, query, folder_path)

        return Response(
            {"folder_path": folder_path},
            content_type=request.accepted_renderer.content_type,  # type: ignore
        )


class StoreAPIView(AsyncApiView):
    parser_classes = [StowMultipartApplicationDicomParser]
    renderer_classes = [StowApplicationDicomJsonRenderer]

    async def handle_request(self, pacs_ae_title: str) -> DicomServer:
        try:
            dest_server = await DicomServer.objects.aget(ae_title=pacs_ae_title)
        except DicomServer.DoesNotExist:
            raise ParseError(f"The specified PACS with AE title: {pacs_ae_title} does not exist.")
        return dest_server

    async def post(
        self,
        request: Request,
        pacs: str,
        study_uid: str = "",
    ) -> Response:
        dest_server = await self.handle_request(pacs)

        if study_uid:
            datasets = [
                dataset
                for dataset in request.data["datasets"]
                if dataset.StudyInstanceUID == study_uid
            ]
        else:
            datasets = request.data["datasets"]

        results = await stow_store(dest_server, datasets)

        return Response(results, content_type=request.accepted_renderer.media_type)  # type: ignore
