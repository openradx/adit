import logging

from rest_framework.exceptions import NotFound, ParseError
from rest_framework.request import Request
from rest_framework.response import Response

from adit.core.models import DicomServer
from adit.dicom_web.views import DicomWebAPIView

from .models import DicomQidoJob, DicomQidoResult, DicomQidoTask
from .renderers import ApplicationDicomJsonRenderer

logger = logging.getLogger(__name__)


class QueryAPIView(DicomWebAPIView):
    renderer_classes = [ApplicationDicomJsonRenderer]

    def handle_request(self, pacs_ae_title: str) -> DicomServer:
        SourceServerSet = DicomServer.objects.filter(ae_title=pacs_ae_title)

        if len(SourceServerSet) < 1:
            raise ParseError(f"The specified PACS with AE title: {pacs_ae_title} does not exist.")
        SourceServer = SourceServerSet[0]

        return SourceServer


class QueryStudyAPIView(QueryAPIView):
    level = "STUDY"

    def get(
        self,
        request: Request,
        pacs: str,
        study_uid: str = "",
        series_uid: str = "",
    ):
        query = str(request.GET.dict())
        SourceServer = self.handle_request(pacs)

        job = DicomQidoJob(
            level=self.level,
            source=SourceServer,
            owner=request.user,
            status=DicomQidoJob.Status.PENDING,
        )
        job.save()
        task = DicomQidoTask(
            study_uid=study_uid,
            series_uid=series_uid,
            query=query,
            job=job,
            task_id=0,
        )
        task.save()
        job.delay()

        while task.status != "SU":
            if task.status == "FA":
                raise NotFound("No dicom objects matching the query exist.")
            task.refresh_from_db()

        results = DicomQidoResult.objects.get(job=job)
        return Response(results.query_results)


class QuerySeriesAPIView(QueryAPIView):
    level = "SERIES"

    def get(
        self,
        request: Request,
        pacs: str,
        study_uid: str,
        series_uid: str = "",
    ):
        query = str(request.GET.dict())
        SourceServer = self.handle_request(pacs)

        job = DicomQidoJob(
            level=self.level,
            source=SourceServer,
            owner=request.user,
            status=DicomQidoJob.Status.PENDING,
        )
        job.save()
        task = DicomQidoTask(
            study_uid=study_uid,
            series_uid=series_uid,
            query=query,
            job=job,
            task_id=0,
        )
        task.save()
        job.delay()

        while task.status != "SU":
            if task.status == "FA":
                raise NotFound("No dicom objects matching the query exist.")
            task.refresh_from_db()

        results = DicomQidoResult.objects.get(job=job)
        return Response(results.query_results)
