
import os
from pathlib import Path

from rest_framework import generics

from django.http import JsonResponse, FileResponse
from django.shortcuts import render

from adit.selective_transfer.models import SelectiveTransferJob
from adit.core.utils.dicom_connector import DicomConnector

from .serializers import SelectiveTransferJobListSerializer, DicomSerializer
from .utils.dicom_web_utils import DicomWebAPIView, DicomWebConnector
from .renderers import DicomMultipartRenderer, DicomJsonRenderer


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
        # Find DICOM Server and create query
        SourceServer, query = self.handle_request(request, *args, **kwargs)

        connector = DicomConnector(SourceServer)

        # C-find study instance with dicom connector
        StudyInstance = connector.find_studies(query)
        
        response = self.request.accepted_renderer.create_response(file=StudyInstance)

        return response

class QuerySeriesAPIView(QueryAPIView):
    LEVEL = "SERIES"
    def get(self, request, *args, **kwargs):
        # Connect to DICOM Server and create query
        SourceServer, query = self.handle_request(request, *args, **kwargs)
        connector = DicomConnector(SourceServer)

        # C-find study instance with dicom connector
        SeriesInstance = connector.find_series(query)

        response = self.request.accepted_renderer.create_response(file=SeriesInstance)

        return response


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
    FOLDER_ADIT = "./temp_WADO-RS_files/"
    renderer_classes = [DicomMultipartRenderer, DicomJsonRenderer]
    Serializer = DicomSerializer


class RetrieveStudyAPIView(RetrieveAPIView):
    LEVEL = "STUDY"
    
    def get(self, request, *args, **kwargs):
        SourceServer, query = self.handle_request(request, *args, **kwargs)
        
        format = self.handle_accept_header(request, *args, **kwargs)

        connector = DicomWebConnector(SourceServer)
        series_list = connector.find_series(query)

        folder_path = Path(self.FOLDER_ADIT) / ("study_"+query["StudyInstanceUID"])
        os.makedirs(folder_path, exist_ok=True)
        file_path = folder_path / "multipart.txt"

        self.Serializer.start_file(self.Serializer, file_path, format["file_format"])
        connector.retrieve_study(
            query["StudyInstanceUID"], 
            series_list,
            format,
            folder_path,
            self.Serializer,
        )
        self.Serializer.end_file(self.Serializer, file_path, format["file_format"])
        
        response = request.accepted_renderer.create_response(file_path=file_path, type=format["file_format"], boundary=self.Serializer.BOUNDARY)
       
        os.remove(file_path)
        os.rmdir(folder_path)

        return response

class RetrieveSeriesAPIView(RetrieveAPIView):
    LEVEL = "SERIES"

    def get(self, request, *args, **kwargs):
        SourceServer, query = self.handle_request(request, *args, **kwargs)
        
        format = self.handle_accept_header(request, *args, **kwargs)

        connector = DicomWebConnector(SourceServer)
        series_uid = query["SeriesInstanceUID"]
        study_uid = query["StudyInstanceUID"]

        folder_path = Path(self.FOLDER_ADIT) / ("series_"+series_uid)
        os.makedirs(folder_path, exist_ok=True)
        file_path = folder_path / "multipart.txt"

        self.Serializer.start_file(self.Serializer, file_path, format["file_format"])
        connector.retrieve_series(
            study_uid, 
            series_uid,
            format,
            folder_path,
            self.Serializer,
        )
        self.Serializer.end_file(self.Serializer, file_path, format["file_format"])
        
        response = FileResponse(
            open(file_path, 'rb'),
            content_type = "multipart/related"
        )
        
        return response


# Selective transfer
class SelectiveTransferJobListAPIView(generics.ListAPIView):
    serializer_class = SelectiveTransferJobListSerializer

    def get_queryset(self):
        return SelectiveTransferJob.objects.filter(owner=self.request.user)


class SelectiveTransferJobDetailAPIView(generics.RetrieveAPIView):
    lookup_field = "id"
    queryset = SelectiveTransferJob.objects.all()
    serializer_class = SelectiveTransferJobListSerializer


