import logging

from django.conf import settings
from django.http import HttpRequest
from rest_framework.exceptions import ParseError
from rest_framework.views import APIView

from adit.core.models import DicomServer

logger = logging.getLogger(__name__)


class DicomWebAPIView(APIView):
    MODE = None
    query = None
    level = None
    TMP_FOLDER: str = settings.WADO_TMP_FOLDER

    def handle_request(
        self, request: HttpRequest, pacs_ae_title: str, study_uid: str, series_uid: str
    ) -> tuple:
        SourceServerSet = DicomServer.objects.filter(ae_title=pacs_ae_title)

        if len(SourceServerSet) < 1:
            raise ParseError(f"The specified PACS with AE title: {pacs_ae_title} does not exist.")
        SourceServer = SourceServerSet[0]

        if self.level == "SERIES" and study_uid == "":
            raise ParseError(
                "To access a series, the corresponding Study Instance UID must be specified."
            )

        return SourceServer, study_uid, series_uid
