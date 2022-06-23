
from executing import Source
from requests import RequestException
import os

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import permissions
from rest_framework import generics

from django.http import HttpResponse, JsonResponse, FileResponse
from django.shortcuts import render
from django.core import serializers

from adit.token_authentication.auth import RestTokenAuthentication
from adit.selective_transfer.models import SelectiveTransferJob
from adit.core.models import TransferJob, DicomNode, DicomServer
from adit.core.utils.dicom_connector import DicomConnector

from .serializers import SelectiveTransferJobListSerializer, DicomStudySerializer
from .utils.dicom_web_utils import DicomWebAPIView, DicomWebConnector
from .models import DicomStudyResponseBodyWriter


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
        "SeriesInstanceUID": "",
        "SeriesDescription": "",
    }
    LEVEL = None

class QueryStudyAPIView(QueryAPIView):
    LEVEL = "STUDY"
    def get(self, request, *args, **kwargs):
        # Find DICOM Server and create query
        SourceServer, query = self.handle_request(request, *args, **kwargs)
        
        connector = DicomConnector(SourceServer)

        # C-find study instance with dicom connector
        StudyInstance = connector.find_studies(query)
        
        return JsonResponse(StudyInstance, safe=False)

class QuerySeriesAPIView(QueryAPIView):
    LEVEL = "SERIES"
    def get(self, request, *args, **kwargs):
        # Connect to DICOM Server and create query
        SourceServer, query = self.handle_request(request, *args, **kwargs)

        connector = DicomConnector(SourceServer)

        # C-find study instance with dicom connector
        SeriesInstance = connector.find_series(query)

        return JsonResponse(SeriesInstance, safe=False)


# WADO-RS
class RetrieveAPIView(DicomWebAPIView):
    MODE = "move"
    query = {
        "StudyInstanceUID": "",
        "PatientID": "",
        "SeriesInstanceUID": "",
        "SeriesDescription": "",
    }
    LEVEL = None
    FOLDER_ADIT = "./temp_dicom_files/"

class RetrieveStudyAPIView(RetrieveAPIView):
    LEVEL = "STUDY"
    ResponseBodySerializer = DicomStudySerializer
    
    def get(self, request, *args, **kwargs):
        SourceServer, query = self.handle_request(request, *args, **kwargs)
        
        connector = DicomWebConnector(SourceServer)

        series_list = connector.find_series(query)

        folders = connector.retrieve_study(
            query["StudyInstanceUID"], 
            series_list,
            folder = self.FOLDER_ADIT,
        )
        study = []
        for folder in folders:
            for instance in os.listdir(folder):
                study.append(folder / instance)

        response_body, boundary = self.ResponseBodySerializer.write(
            self.ResponseBodySerializer,
            study,
            "temp_binary_files/example.txt",
            mode = kwargs.get("mode"),
        )
        
        response = FileResponse(
            open(response_body, 'rb'),
            content_type = "multipart/related; boundary=boundary"
        )
        
        return response

class RetrieveSeriesAPIView(RetrieveAPIView):
    LEVEL = "SERIES"
    def get(self, request, *args, **kwargs):
        SourceServer, query = self.handle_request(request, *args, **kwargs)

        connector = DicomWebConnector(SourceServer)

        connector.retrieve_series(
            query["StudyInstanceUID"],
            query["SeriesInstanceUID"],
            folder = self.FOLDER_ADIT,
        )

        #return HttpResponse(data, content_type='application/octet-stream')
        return HttpResponse("0x0000")


# Selective transfer
class SelectiveTransferJobListAPIView(generics.ListAPIView):
    serializer_class = SelectiveTransferJobListSerializer

    def get_queryset(self):
        return SelectiveTransferJob.objects.filter(owner=self.request.user)


class SelectiveTransferJobDetailAPIView(generics.RetrieveAPIView):
    lookup_field = "id"
    queryset = SelectiveTransferJob.objects.all()
    serializer_class = SelectiveTransferJobListSerializer


