from django.http import HttpResponseBadRequest

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
        SourceServer, study_uid, series_uid, query = self.handle_request(
            request, 
            "QIDO-RS",
            *args, 
            **kwargs
        )
        job = DicomQidoJob(
            level = self.LEVEL,
            source = SourceServer,
            owner = request.user,
            status = DicomQidoJob.Status.PENDING,
        )
        job.save()

        task = DicomQidoTask(
            study_uid = study_uid,
            series_uid = series_uid,
            query = query,
            job = job,
            task_id = 0,
        )
        task.save()
        
        job.delay()
        
        while task.status != "SU":
            if task.status=="FA":
                raise HttpResponseBadRequest("Processing the QIDO-RS request failed.")
            task.refresh_from_db()

        response = self.request.accepted_renderer.create_response(file=job.results.get().query_results)

        return response

class QuerySeriesAPIView(QueryAPIView):
    LEVEL = "SERIES"
    def get(self, request, *args, **kwargs):

        SourceServer, study_uid, series_uid, query = self.handle_request(
            request,
            "QIDO-RS",
            *args, 
            **kwargs,
            )

        job = DicomQidoJob(
            level = self.LEVEL,
            source = SourceServer,
            owner = request.user,
            status = DicomQidoJob.Status.PENDING,
        )
        job.save()

        task = DicomQidoTask(
            study_uid = study_uid,
            series_uid = series_uid,
            query = query,
            job = job,
            task_id = 0,
        )
        task.save()

        job.delay()

        while task.status != "SU":
            if task.status=="FA":
                raise HttpResponseBadRequest("Processing the QIDO-RS request failed.")
            task.refresh_from_db()

        response = self.request.accepted_renderer.create_response(file=job.results.get().query_results)

        return response