import logging

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from adit.dicom_web.views import DicomWebAPIView

from .models import DicomQidoJob, DicomQidoTask
from .renderers import ApplicationDicomJsonRenderer

logger = logging.getLogger(__name__)


class QueryAPIView(DicomWebAPIView):
    level = None
    renderer_classes = [ApplicationDicomJsonRenderer]


class QueryStudyAPIView(QueryAPIView):
    level = "STUDY"

    def get(self, request, *args, **kwargs):
        query = str(request.GET.dict())
        SourceServer, study_uid, series_uid = self.handle_request(
            request,
            pacs_ae_title=kwargs.get("pacs", ""),
            study_uid=kwargs.get("StudyInstanceUID", ""),
            series_uid=kwargs.get("SeriesInstanceUID", ""),
        )
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

        return Response(job.results.get().query_results)


class QuerySeriesAPIView(QueryAPIView):
    level = "SERIES"

    def get(self, request, *args, **kwargs):
        query = str(request.GET.dict())
        SourceServer, study_uid, series_uid = self.handle_request(
            request,
            pacs_ae_title=kwargs.get("pacs", ""),
            study_uid=kwargs.get("StudyInstanceUID", ""),
            series_uid=kwargs.get("SeriesInstanceUID", ""),
        )

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

        return Response(job.results.get().query_results)
