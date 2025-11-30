import json
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Literal, Union, cast

from adit_radis_shared.common.types import AuthenticatedApiRequest, User
from adrf.views import APIView as AsyncApiView
from channels.db import database_sync_to_async
from django.core.exceptions import ValidationError as DRFValidationError
from django.db.models import F, QuerySet
from django.http import StreamingHttpResponse
from django.urls import reverse
from django.utils import timezone
from pydicom import Dataset, Sequence
from rest_framework.exceptions import NotFound, ParseError, UnsupportedMediaType, ValidationError
from rest_framework.response import Response
from rest_framework.utils.mediatypes import media_type_matches

from adit.core.models import DicomServer
from adit.core.utils.dicom_dataset import QueryDataset
from adit.dicom_web.models import APIUsage
from adit.dicom_web.utils.peekable import AsyncPeekable
from adit.dicom_web.validators import (
    validate_pseudonym,
    validate_trial_protocol_id,
    validate_trial_protocol_name,
)

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

    @database_sync_to_async
    def _create_statistic(self, user: User) -> APIUsage:
        statistic, _ = APIUsage.objects.get_or_create(owner=user)
        return statistic

    @database_sync_to_async
    def _finalize_statistic(self, statistic: APIUsage, transfer_size: int = 0) -> None:
        if transfer_size is not None:
            APIUsage.objects.filter(pk=statistic.pk).update(
                total_transfer_size=F("total_transfer_size") + transfer_size,
                total_number_requests=F("total_number_requests") + 1,
                time_last_accessed=timezone.now(),
            )

    @asynccontextmanager
    async def track_session(self, user: User):
        """Context manager to track API session for the duration of a request."""
        session = await self._create_statistic(user)
        try:
            yield session
        finally:
            pass


# TODO: respect permission can_query
class QueryAPIView(WebDicomAPIView):
    renderer_classes = [QidoApplicationDicomJsonRenderer]

    def _extract_query_parameters(
        self,
        request: AuthenticatedApiRequest,
        study_uid: str | None = None,
        series_uid: str | None = None,
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

        if series_uid is not None:
            query["SeriesInstanceUID"] = series_uid

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
        async with self.track_session(request.user) as session:
            query_ds, limit_results = self._extract_query_parameters(request)
            source_server = await self._get_dicom_server(request, ae_title, "source")

            try:
                results = await qido_find(source_server, query_ds, limit_results, "STUDY")
            except ValueError as err:
                logger.warning(f"Invalid DICOMweb study query - {err}")
                raise ValidationError(str(err)) from err

            response_data = [result.dataset.to_json_dict() for result in results]
            await self._finalize_statistic(
                session, transfer_size=len(json.dumps(response_data).encode())
            )
            return Response(response_data)


class QuerySeriesAPIView(QueryAPIView):
    async def get(
        self, request: AuthenticatedApiRequest, ae_title: str, study_uid: str
    ) -> Response:
        async with self.track_session(request.user) as session:
            query_ds, limit_results = self._extract_query_parameters(request, study_uid)
            source_server = await self._get_dicom_server(request, ae_title, "source")

            try:
                results = await qido_find(source_server, query_ds, limit_results, "SERIES")
            except ValueError as err:
                logger.warning(f"Invalid DICOMweb series query - {err}")
                raise ValidationError(str(err)) from err

            response_data = [result.dataset.to_json_dict() for result in results]
            await self._finalize_statistic(
                session, transfer_size=len(json.dumps(response_data).encode())
            )
            return Response(response_data)


class QueryImagesAPIView(QueryAPIView):
    async def get(
        self, request: AuthenticatedApiRequest, ae_title: str, study_uid: str, series_uid: str
    ) -> Response:
        async with self.track_session(request.user) as session:
            query_ds, limit_results = self._extract_query_parameters(request, study_uid, series_uid)
            source_server = await self._get_dicom_server(request, ae_title, "source")

            try:
                results = await qido_find(source_server, query_ds, limit_results, "IMAGE")
            except ValueError as err:
                logger.warning(f"Invalid DICOMweb image query - {err}")
                raise ValidationError(str(err)) from err

            response_data = [result.dataset.to_json_dict() for result in results]
            await self._finalize_statistic(
                session, transfer_size=len(json.dumps(response_data).encode())
            )
            return Response(response_data)


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

    def _get_pseudonym(self, request: AuthenticatedApiRequest) -> str | None:
        pseudonym = request.GET.get("pseudonym")
        if pseudonym is not None:
            try:
                validate_pseudonym(pseudonym)
            except DRFValidationError as e:
                raise ParseError({"pseudonym": e.messages})
            return pseudonym

    def _get_trial_protocol_id(self, request: AuthenticatedApiRequest) -> str | None:
        trial_protocol_id = request.GET.get("trial_protocol_id")
        if trial_protocol_id is not None:
            try:
                validate_trial_protocol_id(trial_protocol_id)
            except DRFValidationError as e:
                raise ParseError({"trial_protocol_id": e.messages})
            return trial_protocol_id

    def _get_trial_protocol_name(self, request: AuthenticatedApiRequest) -> str | None:
        trial_protocol_name = request.GET.get("trial_protocol_name")
        if trial_protocol_name is not None:
            try:
                validate_trial_protocol_name(trial_protocol_name)
            except DRFValidationError as e:
                raise ParseError({"trial_protocol_name": e.messages})
            return trial_protocol_name


class _StreamingSessionWrapper:
    """Wraps streaming content to track transfer size asynchronously."""

    def __init__(self, renderer_generator, session: APIUsage, finalize_func):
        self.renderer_generator = renderer_generator
        self.session = session
        self.finalize_func = finalize_func
        self.total_size = 0

    async def __aiter__(self):
        try:
            async for chunk in self.renderer_generator:
                self.total_size += len(chunk) if isinstance(chunk, bytes) else len(chunk.encode())
                yield chunk
        finally:
            await self.finalize_func(self.session, transfer_size=self.total_size)


class RetrieveStudyAPIView(RetrieveAPIView):
    async def get(
        self, request: AuthenticatedApiRequest, ae_title: str, study_uid: str
    ) -> StreamingHttpResponse:
        async with self.track_session(request.user) as session:
            source_server = await self._get_dicom_server(request, ae_title)
            pseudonym = self._get_pseudonym(request)
            trial_protocol_id = self._get_trial_protocol_id(request)
            trial_protocol_name = self._get_trial_protocol_name(request)

            query = self.query.copy()
            query["StudyInstanceUID"] = study_uid

            images = wado_retrieve(
                source_server,
                query,
                "STUDY",
                pseudonym=pseudonym,
                trial_protocol_id=trial_protocol_id,
                trial_protocol_name=trial_protocol_name,
            )
            images = await self.peek_images(images)

            renderer = cast(DicomWebWadoRenderer, getattr(request, "accepted_renderer"))
            return StreamingHttpResponse(
                streaming_content=_StreamingSessionWrapper(
                    renderer.render(images), session, self._finalize_statistic
                ),
                content_type=renderer.content_type,
            )


class RetrieveStudyMetadataAPIView(RetrieveStudyAPIView):
    async def get(
        self, request: AuthenticatedApiRequest, ae_title: str, study_uid: str
    ) -> Response:
        async with self.track_session(request.user) as session:
            source_server = await self._get_dicom_server(request, ae_title)
            pseudonym = self._get_pseudonym(request)
            trial_protocol_id = self._get_trial_protocol_id(request)
            trial_protocol_name = self._get_trial_protocol_name(request)

            query = self.query.copy()
            query["StudyInstanceUID"] = study_uid

            images = wado_retrieve(
                source_server,
                query,
                "STUDY",
                pseudonym=pseudonym,
                trial_protocol_id=trial_protocol_id,
                trial_protocol_name=trial_protocol_name,
            )
            metadata = await self.extract_metadata(images)

            response_data = {"metadata": metadata}
            await self._finalize_statistic(
                session, transfer_size=len(json.dumps(response_data).encode())
            )

            renderer = cast(DicomWebWadoRenderer, getattr(request, "accepted_renderer"))
            return Response(response_data, content_type=renderer.content_type)


class RetrieveSeriesAPIView(RetrieveAPIView):
    async def get(
        self, request: AuthenticatedApiRequest, ae_title: str, study_uid: str, series_uid: str
    ) -> Response | StreamingHttpResponse:
        async with self.track_session(request.user) as session:
            source_server = await self._get_dicom_server(request, ae_title)
            pseudonym = self._get_pseudonym(request)
            trial_protocol_id = self._get_trial_protocol_id(request)
            trial_protocol_name = self._get_trial_protocol_name(request)

            query = self.query.copy()
            query["StudyInstanceUID"] = study_uid
            query["SeriesInstanceUID"] = series_uid

            images = wado_retrieve(
                source_server,
                query,
                "SERIES",
                pseudonym=pseudonym,
                trial_protocol_id=trial_protocol_id,
                trial_protocol_name=trial_protocol_name,
            )
            images = await self.peek_images(images)

            renderer = cast(DicomWebWadoRenderer, getattr(request, "accepted_renderer"))
            return StreamingHttpResponse(
                streaming_content=_StreamingSessionWrapper(
                    renderer.render(images), session, self._finalize_statistic
                ),
                content_type=renderer.content_type,
            )


class RetrieveSeriesMetadataAPIView(RetrieveSeriesAPIView):
    async def get(
        self, request: AuthenticatedApiRequest, ae_title: str, study_uid: str, series_uid: str
    ) -> Response:
        async with self.track_session(request.user) as session:
            source_server = await self._get_dicom_server(request, ae_title)
            pseudonym = self._get_pseudonym(request)
            trial_protocol_id = self._get_trial_protocol_id(request)
            trial_protocol_name = self._get_trial_protocol_name(request)

            query = self.query.copy()
            query["StudyInstanceUID"] = study_uid
            query["SeriesInstanceUID"] = series_uid

            images = wado_retrieve(
                source_server,
                query,
                "SERIES",
                pseudonym=pseudonym,
                trial_protocol_id=trial_protocol_id,
                trial_protocol_name=trial_protocol_name,
            )
            metadata = await self.extract_metadata(images)

            response_data = {"metadata": metadata}
            await self._finalize_statistic(
                session, transfer_size=len(json.dumps(response_data).encode())
            )

            renderer = cast(DicomWebWadoRenderer, getattr(request, "accepted_renderer"))
            return Response(response_data, content_type=renderer.content_type)


class RetrieveImageAPIView(RetrieveAPIView):
    async def get(
        self,
        request: AuthenticatedApiRequest,
        ae_title: str,
        study_uid: str,
        series_uid: str,
        image_uid: str,
    ) -> Response | StreamingHttpResponse:
        async with self.track_session(request.user) as session:
            source_server = await self._get_dicom_server(request, ae_title)
            pseudonym = self._get_pseudonym(request)
            trial_protocol_id = self._get_trial_protocol_id(request)
            trial_protocol_name = self._get_trial_protocol_name(request)

            query = self.query.copy()
            query["StudyInstanceUID"] = study_uid
            query["SeriesInstanceUID"] = series_uid
            query["SOPInstanceUID"] = image_uid

            images = wado_retrieve(
                source_server,
                query,
                "IMAGE",
                pseudonym=pseudonym,
                trial_protocol_id=trial_protocol_id,
                trial_protocol_name=trial_protocol_name,
            )
            images = await self.peek_images(images)

            renderer = cast(DicomWebWadoRenderer, getattr(request, "accepted_renderer"))
            return StreamingHttpResponse(
                streaming_content=_StreamingSessionWrapper(
                    renderer.render(images), session, self._finalize_statistic
                ),
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
        async with self.track_session(request.user) as session:
            source_server = await self._get_dicom_server(request, ae_title)
            pseudonym = self._get_pseudonym(request)
            trial_protocol_id = self._get_trial_protocol_id(request)
            trial_protocol_name = self._get_trial_protocol_name(request)

            query = self.query.copy()
            query["StudyInstanceUID"] = study_uid
            query["SeriesInstanceUID"] = series_uid
            query["SOPInstanceUID"] = image_uid

            images = wado_retrieve(
                source_server,
                query,
                "IMAGE",
                pseudonym=pseudonym,
                trial_protocol_id=trial_protocol_id,
                trial_protocol_name=trial_protocol_name,
            )
            metadata = await self.extract_metadata(images)

            response_data = {"metadata": metadata}
            await self._finalize_statistic(
                session, transfer_size=len(json.dumps(response_data).encode())
            )

            renderer = cast(DicomWebWadoRenderer, getattr(request, "accepted_renderer"))
            return Response(response_data, content_type=renderer.content_type)


# TODO: respect permission can_store
class StoreImagesAPIView(WebDicomAPIView):
    renderer_classes = [StowApplicationDicomJsonRenderer]

    async def post(
        self,
        request: AuthenticatedApiRequest,
        ae_title: str,
        study_uid: str = "",
    ) -> Response:
        async with self.track_session(request.user) as session:
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
                    logger.debug(f"Stored instance {ds.SOPInstanceUID} to {dest_server.ae_title}")

            response_data = [results]
            await self._finalize_statistic(session, transfer_size=sys.getsizeof(response_data))

            assert request.accepted_renderer is not None
            return Response(response_data, content_type=request.accepted_renderer.media_type)
