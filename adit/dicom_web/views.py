import logging
from typing import AsyncIterator, Literal, cast

from adit_radis_shared.common.types import AuthenticatedApiRequest, User
from adrf.views import APIView as AsyncApiView
from channels.db import database_sync_to_async
from django.db.models import QuerySet
from django.http import StreamingHttpResponse
from django.urls import reverse
from pydicom import Dataset, Sequence
from rest_framework.exceptions import NotFound, ParseError, UnsupportedMediaType, ValidationError
from rest_framework.response import Response
from rest_framework.utils.mediatypes import media_type_matches

from adit.core.models import DicomServer
from adit.dicom_web.utils.peekable import AsyncPeekable

from .parsers import parse_request_in_chunks
from .renderers import (
    DicomWebWadoRenderer,
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
    @database_sync_to_async
    def get_accessible_servers(
        self,
        user: User,
        access_type: Literal["source", "destination"],
    ) -> QuerySet[DicomServer]:
        return DicomServer.objects.accessible_by_user(user, access_type, all_groups=True)

    async def _get_dicom_server(
        self,
        request: AuthenticatedApiRequest,
        ae_title: str,
        access_type: Literal["source", "destination"],
    ) -> DicomServer:
        try:
            accessible_servers = await self.get_accessible_servers(request.user, access_type)
            return await accessible_servers.aget(ae_title=ae_title)
        except DicomServer.DoesNotExist:
            raise NotFound(
                f'Server with AE title "{ae_title}" does not exist or is not accessible.'
            )


# TODO: respect permission can_query
class QueryAPIView(WebDicomAPIView):
    renderer_classes = [QidoApplicationDicomJsonRenderer]


class QueryStudiesAPIView(QueryAPIView):
    async def get(
        self,
        request: AuthenticatedApiRequest,
        ae_title: str,
    ) -> Response:
        query: dict[str, str] = {}
        for key, value in request.GET.items():
            query[key] = value

        source_server = await self._get_dicom_server(request, ae_title, "source")

        try:
            results = await qido_find(source_server, query, "STUDY")
        except ValueError as err:
            logger.warn(f"Invalid DICOMweb study query - {err}")
            raise ValidationError(str(err)) from err

        return Response([result.dataset.to_json_dict() for result in results])


class QuerySeriesAPIView(QueryAPIView):
    async def get(
        self, request: AuthenticatedApiRequest, ae_title: str, study_uid: str
    ) -> Response:
        query: dict[str, str] = {}
        for key, value in request.GET.items():
            query[key] = value

        query["StudyInstanceUID"] = study_uid

        source_server = await self._get_dicom_server(request, ae_title, "source")

        try:
            results = await qido_find(source_server, query, "SERIES")
        except ValueError as err:
            logger.warn(f"Invalid DICOMweb series query - {err}")
            raise ValidationError(str(err)) from err

        return Response([result.dataset.to_json_dict() for result in results])


# TODO: respect permission can_retrieve
class RetrieveAPIView(WebDicomAPIView):
    query: dict = {
        "StudyInstanceUID": "",
        "PatientID": "",
        "SeriesInstanceUID": "",
        "SeriesDescription": "",
    }
    renderer_classes = [WadoMultipartApplicationDicomRenderer, WadoApplicationDicomJsonRenderer]

    async def _get_dicom_server(
        self, request: AuthenticatedApiRequest, ae_title: str
    ) -> DicomServer:
        source_server = await super()._get_dicom_server(request, ae_title, "source")

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

        return source_server

    async def extract_metadata(self, instances: AsyncIterator[Dataset]) -> list[dict]:
        metadata: list[dict] = []
        async for ds in instances:
            if hasattr(ds, "PixelData"):
                del ds.PixelData
            metadata.append(ds.to_json_dict())
        return metadata


class RetrieveStudyAPIView(RetrieveAPIView):
    async def get(
        self, request: AuthenticatedApiRequest, ae_title: str, study_uid: str
    ) -> StreamingHttpResponse:
        source_server = await self._get_dicom_server(request, ae_title)

        query = self.query.copy()
        query["StudyInstanceUID"] = study_uid

        instances = wado_retrieve(source_server, query)
        instances = AsyncPeekable(instances)

        # In the middle of a StreamingHttpResponse we can't just throw an exception anymore to
        # just return a error response as the stream has already started. Thats why we peek
        # here and throw an exception to return an error response if something initially
        # went wrong. If the in middle of the StreamingHttpResponse an error happens (not
        # reachable PACS server or so) we return a error message inside the streamed response,
        # but this just leads to a not readable DICOM file on the client side.
        try:
            await instances.peek()
        except StopAsyncIteration:
            pass
        except Exception as err:
            logger.exception(err)
            raise

        renderer = cast(DicomWebWadoRenderer, getattr(request, "accepted_renderer"))

        return StreamingHttpResponse(
            streaming_content=renderer.render(instances),
            content_type=renderer.content_type,
        )


class RetrieveStudyMetadataAPIView(RetrieveStudyAPIView):
    async def get(
        self, request: AuthenticatedApiRequest, ae_title: str, study_uid: str
    ) -> Response:
        source_server = await self._get_dicom_server(request, ae_title)

        query = self.query.copy()
        query["StudyInstanceUID"] = study_uid

        instances = wado_retrieve(source_server, query)

        metadata = await self.extract_metadata(instances)

        renderer = cast(DicomWebWadoRenderer, getattr(request, "accepted_renderer"))

        return Response({"metadata": metadata}, content_type=renderer.content_type)


class RetrieveSeriesAPIView(RetrieveAPIView):
    async def get(
        self, request: AuthenticatedApiRequest, ae_title: str, study_uid: str, series_uid: str
    ) -> Response | StreamingHttpResponse:
        source_server = await self._get_dicom_server(request, ae_title)

        query = self.query.copy()
        query["StudyInstanceUID"] = study_uid
        query["SeriesInstanceUID"] = series_uid

        instances = wado_retrieve(source_server, query)
        instances = AsyncPeekable(instances)

        # See comment in RetrieveStudyAPIView
        try:
            await instances.peek()
        except StopAsyncIteration:
            pass
        except Exception as err:
            logger.exception(err)
            raise

        renderer = cast(DicomWebWadoRenderer, getattr(request, "accepted_renderer"))

        return StreamingHttpResponse(
            streaming_content=renderer.render(instances),
            content_type=renderer.content_type,
        )


class RetrieveSeriesMetadataAPIView(RetrieveSeriesAPIView):
    async def get(
        self, request: AuthenticatedApiRequest, ae_title: str, study_uid: str, series_uid: str
    ) -> Response:
        source_server = await self._get_dicom_server(request, ae_title)

        query = self.query.copy()
        query["StudyInstanceUID"] = study_uid
        query["SeriesInstanceUID"] = series_uid

        instances = wado_retrieve(source_server, query)

        metadata = await self.extract_metadata(instances)

        renderer = cast(DicomWebWadoRenderer, getattr(request, "accepted_renderer"))

        return Response({"metadata": metadata}, content_type=renderer.content_type)


# TODO: respect permission can_store
class StoreInstancesAPIView(WebDicomAPIView):
    renderer_classes = [StowApplicationDicomJsonRenderer]

    async def post(
        self,
        request: AuthenticatedApiRequest,
        ae_title: str,
        study_uid: str = "",
    ) -> Response:
        content_type: str = request.content_type  # type: ignore
        if not media_type_matches("multipart/related; type=application/dicom", content_type):
            raise UnsupportedMediaType(content_type)

        dest_server = await self._get_dicom_server(request, ae_title, "destination")

        results: Dataset = Dataset()
        results.ReferencedSOPSequence = Sequence([])
        results.FailedSOPSequence = Sequence([])

        async for ds in parse_request_in_chunks(request):
            if ds is None:
                continue

            logger.debug(f"Received instance {ds.SOPInstanceUID} via STOW-RS")

            if study_uid:
                results.RetrieveURL = reverse(
                    "wado_rs-studies_with_study_uid",
                    args=[dest_server.ae_title, ds.StudyInstanceUID],
                )
                if ds.StudyInstanceUID != study_uid:
                    continue

            logger.debug(f"Storing instance {ds.SOPInstanceUID} to {dest_server.ae_title}")
            result_ds, failed = await stow_store(dest_server, ds)

            if failed:
                logger.debug(
                    f"Storing instance {ds.SOPInstanceUID} to {dest_server.ae_title} failed"
                )
                results.FailedSOPSequence.append(result_ds)
            else:
                results.ReferencedSOPSequence.append(result_ds)
                logger.debug(
                    f"Successfully stored instance {ds.SOPInstanceUID} to {dest_server.ae_title}"
                )

        return Response([results], content_type=request.accepted_renderer.media_type)  # type: ignore
