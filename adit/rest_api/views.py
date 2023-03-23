import logging
import os
from pathlib import Path
from typing import Type
from django.conf import settings
from django.http import HttpRequest
from rest_framework import generics
from rest_framework.exceptions import NotAcceptable, ParseError
from rest_framework.views import APIView
from werkzeug.http import parse_options_header
from adit.core.models import DicomServer
from adit.selective_transfer.models import SelectiveTransferJob
from .serializers import DicomWebSerializer, SelectiveTransferJobListSerializer

logger = logging.getLogger(__name__)


class DicomWebAPIView(APIView):
    MODE = None
    query = None

    def handle_request(self, request: Type[HttpRequest], *args: dict, **kwargs: dict) -> tuple:
        pacs_ae_title = kwargs.get("pacs", None)
        SourceServerSet = DicomServer.objects.filter(ae_title=pacs_ae_title)
        if len(SourceServerSet) < 1:
            raise ParseError(f"The specified PACS with AE title: {pacs_ae_title} does not exist.")
        SourceServer = SourceServerSet[0]

        study_uid = kwargs.get("StudyInstanceUID", "")
        series_uid = kwargs.get("SeriesInstanceUID", "")
        if self.LEVEL == "SERIES" and study_uid is None:
            raise ParseError(
                "To access a series, the corresponding Study Instance UID must be specified."
            )

        return SourceServer, study_uid, series_uid

    def handle_accept_header(
        self, request: Type[HttpRequest], *args: dict, **kwargs: dict
    ) -> tuple:
        serializer = DicomWebSerializer()
        try:
            if kwargs.get("mode") == "metadata":
                mode = "meta"
                supported_content_types = serializer.meta_content_types
                default_content_type = serializer.meta_d_content_type
            else:
                mode = "bulk"
                supported_content_types = serializer.bulk_content_types
                default_content_type = serializer.bulk_d_content_type

            accept_headers = request.headers.get("Accept")
            if accept_headers is None:
                try:
                    accept_headers = request.META["headers"].get("Accept")
                except KeyError:
                    pass

            if accept_headers is not None:
                media_type, options = parse_options_header(accept_headers)
                boundary = options.get("boundary", settings.DEFAULT_BOUNDARY)
                if media_type == "*/*":
                    content_type = default_content_type
                elif media_type in serializer.MULTIPART_MEDIA_TYPES:
                    if options["type"] in list(
                        set(supported_content_types) & set(serializer.multipart_content_types)
                    ):
                        content_type = options["type"]
                elif media_type in serializer.MEDIA_TYPES:
                    content_type = media_type

        except SystemError:
            raise NotAcceptable(
                f"Media type not accepted. Supported media types for retrieve mode {mode} are: {supported_content_types}."
            )

        try:
            content_type
        except NameError:
            raise NotAcceptable(
                f"Media type not accepted. Supported media types for retrieve mode {mode} are: {supported_content_types}."
            )

        logger.debug(f"Accepted file format: {content_type} for retrieve mode: {mode}.")
        return mode, content_type, boundary

    def generate_temp_files(self, study_uid: str, series_uid: str, level: str) -> tuple:
        folder_path = Path(self.FOLDER_ADIT)
        if level == "STUDY":
            folder_path = folder_path / ("study_" + study_uid)
            dicom_files_path = folder_path / "dicom_files"
            os.makedirs(folder_path, exist_ok=True)
            os.makedirs(dicom_files_path, exist_ok=True)
            file_path = folder_path / "response.txt"
        elif level == "SERIES":
            folder_path = folder_path / ("series_" + series_uid)
            dicom_files_path = folder_path / "dicom_files"
            os.makedirs(folder_path, exist_ok=True)
            os.makedirs(dicom_files_path, exist_ok=True)
            file_path = folder_path / "response.txt"

        return folder_path, file_path


# Selective transfer
class SelectiveTransferJobListAPIView(generics.ListAPIView):
    serializer_class = SelectiveTransferJobListSerializer

    def get_queryset(self):
        return SelectiveTransferJob.objects.filter(owner=self.request.user)


class SelectiveTransferJobDetailAPIView(generics.RetrieveAPIView):
    lookup_field = "id"
    queryset = SelectiveTransferJob.objects.all()
    serializer_class = SelectiveTransferJobListSerializer
