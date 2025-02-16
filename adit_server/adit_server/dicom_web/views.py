import logging
from typing import AsyncIterator, Literal, Union, cast

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

from adit_server.core.models import DicomServer
from adit_server.core.utils.dicom_dataset import QueryDataset
from adit_server.dicom_web.utils.peekable import AsyncPeekable

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

    def _extract_query_parameters(
        self, request: AuthenticatedApiRequest, study_uid: str | None = None
    ) -> tuple[QueryDataset, Union[int, None]]:
        """
        Filters a valid DICOMweb requests GET parameters and returns a QueryDataset and a
        limit value to match ADIT implementation
        """
        query: dict[str, str] = {}
        for key, value in request.GET.items():
            assert isinstance(value, str)
            if key == "includefield":
                continue
            else:
                query[key] = value

        if study_uid is not None:
            query["StudyInstanceUID"] = study_uid

        limit_results = None
        if "limit" in query:
            limit_results = int(query.pop("limit"))

        query_ds = QueryDataset.from_dict(query)
        query_ds.ensure_elements(*request.GET.getlist("includefield"))
        return query_ds, limit_results


class QueryStudiesAPIView(QueryAPIView):
    async def get(
        self,
        request: AuthenticatedApiRequest,
        ae_title: str,
    ) -> Response:
        query_ds, limit_results = self._extract_query_parameters(request)
        source_server = await self._get_dicom_server(request, ae_title, "source")

        try:
            results = await qido_find(source_server, query_ds, limit_results, "STUDY")
        except ValueError as err:
            logger.warning(f"Invalid DICOMweb study query - {err}")
            raise ValidationError(str(err)) from err

        return Response([result.dataset.to_json_dict() for result in results])


class QuerySeriesAPIView(QueryAPIView):
    async def get(
        self, request: AuthenticatedApiRequest, ae_title: str, study_uid: str
    ) -> Response:
        query_ds, limit_results = self._extract_query_parameters(request, study_uid)
        source_server = await self._get_dicom_server(request, ae_title, "source")

        try:
            results = await qido_find(source_server, query_ds, limit_results, "SERIES")
        except ValueError as err:
            logger.warning(f"Invalid DICOMweb series query - {err}")
            raise ValidationError(str(err)) from err

        return Response([result.dataset.to_json_dict() for result in results])


class QueryImagesAPIView(QueryAPIView):
    async def get(
        self, request: AuthenticatedApiRequest, ae_title: str, series_uid: str
    ) -> Response:
        query_ds, limit_results = self._extract_query_parameters(request, series_uid)
        source_server = await self._get_dicom_server(request, ae_title, "source")

        try:
            results = await qido_find(source_server, query_ds, limit_results, "IMAGE")
        except ValueError as err:
            logger.warning(f"Invalid DICOMweb image query - {err}")
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

    async def peek_images(self, images: AsyncIterator[Dataset]) -> AsyncPeekable[Dataset]:
        # In the middle of a StreamingHttpResponse we can't just throw an exception anymore to
        # just return a error response as the stream has already started. Thats why we peek
        # the first image here and throw an exception to return an error response if something
        # initially went wrong. If in middle of the StreamingHttpResponse an error happens (e.g.
        # PACS not reachable anymore) we return an error message inside the streamed response,
        # but this by default just leads to a not readable DICOM file on the client side.
        peekable_images = AsyncPeekable(images)
        try:
            await peekable_images.peek()
        except StopAsyncIteration:
            pass
        except Exception as err:
            logger.exception(err)
            raise

        return peekable_images

    async def extract_metadata(self, images: AsyncIterator[Dataset]) -> list[dict]:
        metadata: list[dict] = []
        async for image in images:
            if hasattr(image, "PixelData"):
                del image.PixelData
            metadata.append(image.to_json_dict())
        return metadata


class RetrieveStudyAPIView(RetrieveAPIView):
    async def get(
        self, request: AuthenticatedApiRequest, ae_title: str, study_uid: str
    ) -> StreamingHttpResponse:
        source_server = await self._get_dicom_server(request, ae_title)

        query = self.query.copy()
        query["StudyInstanceUID"] = study_uid

        images = wado_retrieve(source_server, query, "STUDY")
        images = await self.peek_images(images)

        renderer = cast(DicomWebWadoRenderer, getattr(request, "accepted_renderer"))
        return StreamingHttpResponse(
            streaming_content=renderer.render(images),
            content_type=renderer.content_type,
        )


class RetrieveStudyMetadataAPIView(RetrieveStudyAPIView):
    async def get(
        self, request: AuthenticatedApiRequest, ae_title: str, study_uid: str
    ) -> Response:
        source_server = await self._get_dicom_server(request, ae_title)

        query = self.query.copy()
        query["StudyInstanceUID"] = study_uid

        images = wado_retrieve(source_server, query, "STUDY")
        metadata = await self.extract_metadata(images)

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

        images = wado_retrieve(source_server, query, "SERIES")
        images = await self.peek_images(images)

        renderer = cast(DicomWebWadoRenderer, getattr(request, "accepted_renderer"))
        return StreamingHttpResponse(
            streaming_content=renderer.render(images),
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

        images = wado_retrieve(source_server, query, "SERIES")
        metadata = await self.extract_metadata(images)

        renderer = cast(DicomWebWadoRenderer, getattr(request, "accepted_renderer"))
        return Response({"metadata": metadata}, content_type=renderer.content_type)


class RetrieveImageAPIView(RetrieveAPIView):
    async def get(
        self,
        request: AuthenticatedApiRequest,
        ae_title: str,
        study_uid: str,
        series_uid: str,
        image_uid: str,
    ) -> Response | StreamingHttpResponse:
        source_server = await self._get_dicom_server(request, ae_title)

        query = self.query.copy()
        query["StudyInstanceUID"] = study_uid
        query["SeriesInstanceUID"] = series_uid
        query["SOPInstanceUID"] = image_uid

        images = wado_retrieve(source_server, query, "IMAGE")
        images = await self.peek_images(images)

        renderer = cast(DicomWebWadoRenderer, getattr(request, "accepted_renderer"))
        return StreamingHttpResponse(
            streaming_content=renderer.render(images),
            content_type=renderer.content_type,
        )


class RetrieveImageMetadataAPIView(RetrieveImageAPIView):
    async def get(
        self,
        request: AuthenticatedApiRequest,
        ae_title: str,
        study_uid: str,
        series_uid: str,
        image_uid: str,
    ) -> Response:
        source_server = await self._get_dicom_server(request, ae_title)

        query = self.query.copy()
        query["StudyInstanceUID"] = study_uid
        query["SeriesInstanceUID"] = series_uid
        query["SOPInstanceUID"] = image_uid

        images = wado_retrieve(source_server, query, "IMAGE")
        metadata = await self.extract_metadata(images)

        renderer = cast(DicomWebWadoRenderer, getattr(request, "accepted_renderer"))
        return Response({"metadata": metadata}, content_type=renderer.content_type)


# TODO: respect permission can_store
class StoreImagesAPIView(WebDicomAPIView):
    renderer_classes = [StowApplicationDicomJsonRenderer]

    async def post(
        self,
        request: AuthenticatedApiRequest,
        ae_title: str,
        study_uid: str = "",
    ) -> Response:
        content_type: str = request.content_type
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
                    "wado_rs-study_with_study_uid",
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

        assert request.accepted_renderer is not None
        return Response([results], content_type=request.accepted_renderer.media_type)
