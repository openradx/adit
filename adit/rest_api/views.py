import os
from pathlib import Path
import logging
from typing import Type

from django.http import HttpRequest
from django.conf import settings

from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.exceptions import NotAcceptable, ParseError

from adit.core.models import DicomServer
from adit.selective_transfer.models import SelectiveTransferJob
from .serializers import DicomWebSerializer, SelectiveTransferJobListSerializer


logger = logging.getLogger(__name__)


class DicomWebAPIView(APIView):
    MODE = None
    query = None

    def handle_request(
        self, request: Type[HttpRequest], *args: dict, **kwargs: dict
    ) -> tuple:
        pacs_ae_title = kwargs.get("pacs", None)
        SourceServerSet = DicomServer.objects.filter(ae_title=pacs_ae_title)
        if len(SourceServerSet) < 1:
            raise ParseError(
                f"The specified PACS with AE title: {pacs_ae_title} does not exist."
            )
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

            accept_headers = self._format_accept_header(request.META["HTTP_ACCEPT"])
            for header in accept_headers:
                boundary = settings.DEFAULT_BOUNDARY
                if header["media_type"] in serializer.MULTIPART_MEDIA_TYPES:
                    if (
                        header["type"] in supported_content_types
                        and header["type"] in serializer.multipart_content_types
                    ):
                        content_type = header["type"]
                        if header.get("boundary") is not None:
                            boundary = header["boundary"]
                elif header["media_type"] in serializer.MEDIA_TYPES:
                    content_type = header["media_type"]
                elif header["media_type"] == "*/*":
                    content_type = default_content_type

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

    def _format_accept_header(self, accept_header_str: str) -> tuple:
        chars_to_remove = [" ", "'", '"']
        for char in chars_to_remove:
            accept_header_str = accept_header_str.replace(char, "")
        accept_headers = [header.split(";") for header in accept_header_str.split(",")]
        accept_headers_formated = [{} for i in range(len(accept_headers))]
        for j in range(len(accept_headers)):
            accept_header = accept_headers[j]
            accept_headers_formated[j]["media_type"] = accept_header[0]
            for i in range(1, len(accept_header)):
                key, value = accept_header[i].split("=")
                accept_headers_formated[j][key] = value

        return accept_headers_formated

    def generate_temp_files(self, study_uid: str, series_uid: str, level: str) -> tuple:
        folder_path = Path(self.FOLDER_ADIT)
        if level == "STUDY":
            folder_path = folder_path / ("study_" + study_uid)
            os.makedirs(folder_path, exist_ok=True)
            file_path = folder_path / "response.txt"
        elif level == "SERIES":
            folder_path = folder_path / ("series_" + series_uid)
            os.makedirs(folder_path, exist_ok=True)
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
