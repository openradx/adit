import logging
import os
from pathlib import Path
from typing import Literal

from adrf.views import APIView as AsyncApiView
from adrf.views import sync_to_async
from django.conf import settings
from rest_framework.exceptions import NotAcceptable, NotFound, ParseError, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from adit.core.models import DicomServer
from adit.core.types import AuthenticatedRequest

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


class WebDicomAPIView(AsyncApiView):
    @sync_to_async
    def _fetch_dicom_server(
        self,
        request: AuthenticatedRequest,
        ae_title: str,
        access_type: Literal["source", "destination"],
    ) -> DicomServer:
        try:
            accessible_servers = DicomServer.objects.accessible_by_user(request.user, access_type)
            return accessible_servers.get(ae_title=ae_title)
        except DicomServer.DoesNotExist:
            raise NotFound(
                f'Server with AE title "{ae_title}" does not exist or is not accessible.'
            )


class QueryAPIView(WebDicomAPIView):
    level: Literal["STUDY", "SERIES"]
    renderer_classes = [QidoApplicationDicomJsonRenderer]


class QueryStudyAPIView(QueryAPIView):
    level = "STUDY"

    async def get(
        self,
        request: AuthenticatedRequest,
        ae_title: str,
    ) -> Response:
        query: dict[str, str] = {}
        for key, value in request.GET.items():
            query[key] = value

        source_server = await self._fetch_dicom_server(request, ae_title, "source")

        try:
            results = await qido_find(source_server, query, self.level)
        except ValueError as err:
            logger.warn(f"Invalid DICOMweb study query - {err}")
            raise ValidationError(str(err)) from err

        return Response([result.dataset.to_json_dict() for result in results])


class QuerySeriesAPIView(QueryAPIView):
    level = "SERIES"

    async def get(
        self,
        request: AuthenticatedRequest,
        ae_title: str,
        study_uid: str = "",
    ) -> Response:
        query: dict[str, str] = {}
        for key, value in request.GET.items():
            query[key] = value

        if not study_uid:
            # In contrast to the DICOMweb standard, ADIT can't support querying series without
            # a StudyInstanceUID as the data may be fetched from a DIMSE source which doesn't
            # support querying series without a StudyInstanceUID.
            raise ValidationError(
                "ADIT does not support querying series without a StudyInstanceUID."
            )

        query["StudyInstanceUID"] = study_uid
        source_server = await self._fetch_dicom_server(request, ae_title, "source")

        try:
            results = await qido_find(source_server, query, self.level)
        except ValueError as err:
            logger.warn(f"Invalid DICOMweb series query - {err}")
            raise ValidationError(str(err)) from err

        return Response([result.dataset.to_json_dict() for result in results])


class RetrieveAPIView(WebDicomAPIView):
    level: Literal["STUDY", "SERIES"]
    query: dict = {
        "StudyInstanceUID": "",
        "PatientID": "",
        "SeriesInstanceUID": "",
        "SeriesDescription": "",
    }
    renderer_classes = [WadoMultipartApplicationDicomRenderer, WadoApplicationDicomJsonRenderer]

    async def handle_request(
        self,
        request: AuthenticatedRequest,
        ae_title: str,
        mode: str,
        study_uid: str,
        series_uid: str = "",
    ) -> tuple[DicomServer, Path]:
        await self._check_renderer_mode(request, mode)

        source_server = await self._fetch_dicom_server(request, ae_title, "source")

        # A PACS without the below capabilities is not supported. Even when it has Patient Root GET
        # or MOVE support, because the DICOMweb client can't provide a PatientID in a WADO request.
        # DICOMweb does never seem to work on the Patient level.
        if not (
            source_server.study_root_get_support
            or source_server.study_root_move_support
            or source_server.dicomweb_wado_support
        ):
            raise ParseError(
                f"The specified server with AE title '{ae_title}' does not support WADO-RS."
            )

        folder_path = await self._generate_temp_folder(study_uid, series_uid, self.level)

        return source_server, folder_path

    async def _check_renderer_mode(self, request: Request, mode: str):
        if mode != request.accepted_renderer.mode:  # type: ignore
            raise NotAcceptable(
                "Media type {} is not supported for retrieve mode {}".format(
                    request.accepted_renderer.media_type, mode  # type: ignore
                )
            )

    async def _generate_temp_folder(
        self, study_uid: str, series_uid: str, level: Literal["STUDY", "SERIES"]
    ) -> Path:
        folder_path = Path(settings.TEMP_DICOM_DIR) / "wado"
        if level == "STUDY":
            folder_path = folder_path / ("study_" + study_uid)
            await sync_to_async(os.makedirs)(folder_path, exist_ok=True)
        elif level == "SERIES":
            folder_path = folder_path / ("series_" + series_uid)
            await sync_to_async(os.makedirs)(folder_path, exist_ok=True)

        return folder_path


class RetrieveStudyAPIView(RetrieveAPIView):
    level = "STUDY"

    async def get(
        self,
        request: AuthenticatedRequest,
        ae_title: str,
        study_uid: str,
        mode: str = "bulk",
    ) -> Response:
        source_server, folder_path = await self.handle_request(request, ae_title, mode, study_uid)
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
        request: AuthenticatedRequest,
        ae_title: str,
        study_uid: str,
        series_uid: str,
        mode: str = "bulk",
    ) -> Response:
        source_server, folder_path = await self.handle_request(
            request, ae_title, mode, study_uid, series_uid
        )
        query = self.query.copy()
        query["StudyInstanceUID"] = study_uid
        query["SeriesInstanceUID"] = series_uid

        # TODO: We should make sure in a finally block that the folder is deleted.
        await wado_retrieve(source_server, query, folder_path)

        return Response(
            {"folder_path": folder_path},
            content_type=request.accepted_renderer.content_type,  # type: ignore
        )


class StoreAPIView(WebDicomAPIView):
    parser_classes = [StowMultipartApplicationDicomParser]
    renderer_classes = [StowApplicationDicomJsonRenderer]

    async def handle_request(self, request: AuthenticatedRequest, ae_title: str) -> DicomServer:
        return await self._fetch_dicom_server(request, ae_title, "destination")

    async def post(
        self,
        request: AuthenticatedRequest,
        ae_title: str,
        study_uid: str = "",
    ) -> Response:
        dest_server = await self.handle_request(request, ae_title)

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
