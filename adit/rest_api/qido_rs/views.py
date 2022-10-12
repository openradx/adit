from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

from ..views import DicomWebAPIView
from ..renderers import DicomJsonRenderer
from .models import (
    DicomQidoJob,
    DicomQidoTask,
)

# QIDO-RS
class QueryAPIView(DicomWebAPIView):
    LEVEL = None
    renderer_classes = [DicomJsonRenderer]


class QueryStudyAPIView(QueryAPIView):
    LEVEL = "STUDY"

    def get(self, request, *args, **kwargs):
        query = str(request.GET.dict())
        SourceServer, study_uid, series_uid = self.handle_request(
            request, *args, **kwargs
        )

        job = DicomQidoJob(
            level=self.LEVEL,
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
                raise NotFound(f"No dicom objects matching the query exist.")
            task.refresh_from_db()

        response = self.request.accepted_renderer.create_response(
            file=job.results.get().query_results
        )

        return response


class QuerySeriesAPIView(QueryAPIView):
    LEVEL = "SERIES"

    def get(self, request, *args, **kwargs):
        query = str(request.GET.dict())
        SourceServer, study_uid, series_uid = self.handle_request(
            request,
            *args,
            **kwargs,
        )

        job = DicomQidoJob(
            level=self.LEVEL,
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
                raise NotFound(f"No dicom objects matching the query exist.")
            task.refresh_from_db()

        response = self.request.accepted_renderer.create_response(
            file=job.results.get().query_results
        )

        return response
