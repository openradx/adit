from django.http import HttpResponseBadRequest

from ..views import DicomWebAPIView
from ..renderers import DicomJsonRenderer
from .models import (
    DicomQidoJob,
    DicomQidoTask,
)

# QIDO-RS
class QueryAPIView(DicomWebAPIView):
    query = {
        "StudyInstanceUID": "",
        "PatientID": "",
        "PatientName": "",
        "PatientBithDate": "",
        "AccessionNumber": "",
        "StudyDate": "",
        "ModalitiesInStudy": "",
        "NumberOfStudyRelatedInstances": "",
        "NumberOfSeriesRelatedInstances": "",
        "SeriesInstanceUID": "",
        "SOPInstaceUID": "",
        "SeriesDescription": "",
    }
    LEVEL = None
    renderer_classes = [DicomJsonRenderer]


class QueryStudyAPIView(QueryAPIView):
    LEVEL = "STUDY"
    def get(self, request, *args, **kwargs):

        SourceServer, query = self.handle_request(request, *args, **kwargs)

        job = DicomQidoJob(
            level = self.LEVEL,
            source = SourceServer,
            owner = request.user,
            status = DicomQidoJob.Status.PENDING,
        )
        job.save()

        task = DicomQidoTask(
            study_uid = query.get("StudyInstanceUID"),
            series_uid = query.get("SeriesInstanceUID"),
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

        SourceServer, query = self.handle_request(request, *args, **kwargs)

        job = DicomQidoJob(
            level = self.LEVEL,
            source = SourceServer,
            owner = request.user,
            status = DicomQidoJob.Status.PENDING,
        )
        job.save()

        task = DicomQidoTask(
            study_uid = query.get("StudyInstanceUID"),
            series_uid = query.get("SeriesInstanceUID"),
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