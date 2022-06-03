
from requests import RequestException
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import permissions
from rest_framework import generics

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.core import serializers

from adit.token_authentication.auth import RestTokenAuthentication
from adit.selective_transfer.models import SelectiveTransferJob
from adit.core.models import TransferJob, DicomNode, DicomServer
from adit.core.utils.dicom_connector import DicomConnector

from .serializers import SelectiveTransferJobListSerializer
from .utils.request_handler import handle_request


# Create your views here.
class TestView(APIView):
    authentication_classes = [RestTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return HttpResponse("HI")

# QIDO-RS
class QueryAPIView(APIView):
    query = {
        "PatientID": "",
        "PatientName": "",
        "PatientBithDate": "",
        "AccessionNumber": "",
        "StudyDate": "",
        "ModalitiesInStudy": "",
        "NumberOfStudyRelatedInstances": "",
        "SeriesInstanceUID": "",
        "SeriesDescription": "",
    }

    def get(self, request, *args, **kwargs):
        SourceServer = handle_request(request, *args, **kwargs)

        # Create query
        self.query.update(request.query_params.copy())

        StudyInstanceUID = kwargs.get("StudyInstanceUID")
        if not StudyInstanceUID is None:
            self.query["StudyInstanceUID"] = StudyInstanceUID
            query_level = "SERIES"
        else:
            query_level = "STUDY"

        # Connect to PACS and c-find study
        connector = DicomConnector(SourceServer)
        connector.open_connection("find")
        if query_level == "SERIES":
            StudyInstance = connector.find_series(self.query)
        elif query_level == "STUDY":
            StudyInstance = connector.find_studies(self.query)
        connector.close_connection()
        
        return JsonResponse(StudyInstance, safe=False)


# WAIDO-RS


# Selective transfer
class SelectiveTransferJobListAPIView(generics.ListAPIView):
    serializer_class = SelectiveTransferJobListSerializer

    def get_queryset(self):
        return SelectiveTransferJob.objects.filter(owner=self.request.user)


class SelectiveTransferJobDetailAPIView(generics.RetrieveAPIView):
    lookup_field = "id"
    queryset = SelectiveTransferJob.objects.all()
    serializer_class = SelectiveTransferJobListSerializer


