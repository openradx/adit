from executing import Source
from requests import RequestException
from pathlib import Path
import logging

from django.core import serializers
from rest_framework.views import APIView

from adit.core.models import TransferJob, DicomNode, DicomServer
from adit.core.utils.dicom_connector import DicomConnector, sanitize_dirname



logger = logging.getLogger(__name__)



class DicomWebAPIView(APIView):
    MODE = None
    query = None

    def handle_request(self, request, *args, **kwargs):
        # Find PACS and connect
        pacs_ae_title = kwargs.get("pacs", None)
        SourceServerSet = DicomServer.objects.filter(ae_title=pacs_ae_title)
        if len(SourceServerSet) != 1:
            raise RequestException(f"The specified PACS with AE title: {pacs_ae_title} does not exist or multiple Entities with this title exist.")
        SourceServer = SourceServerSet[0]

        # update query
        query = self.query.copy()
        query.update(request.query_params.copy())

        StudyInstanceUID = kwargs.get("StudyInstanceUID")
        if self.LEVEL == "SERIES" and StudyInstanceUID is None:
            raise NotImplementedError("Query for series without specified study is not yet supported.")
        SeriesInstanceUID = kwargs.get("SeriesInstanceUID")
        if not StudyInstanceUID is None:
            query["StudyInstanceUID"] = StudyInstanceUID
        if not SeriesInstanceUID is None:
            query["SeriesInstanceUID"] = StudyInstanceUID

        # TODO: Implement accept header handler
        
        return SourceServer, query



class DicomWebConnector(DicomConnector):
    def retrieve_study(
        self, 
        study_uid, 
        series_list,
        folder,
        patient_id = "",
        modality = None,
        modifier_callback = None,
    ):
        folders = []
        for series in series_list:
            series_uid = series["SeriesInstanceUID"]

            series_folder_name = sanitize_dirname(series["SeriesDescription"])
            download_path = Path(folder) / series_folder_name

            self.download_series(
                patient_id, study_uid, series_uid, download_path, modifier_callback
            )
            
            folders.append(download_path)
        
        logger.debug("Successfully downloaded study %s.", study_uid)
        
        return folders
    
    def retrieve_series(
        self,
        study_uid,
        series,
        folder,
        patient_id = "",
        modality=None,
        modifier_callback=None,
    ):
        series_uid = series["SeriesInstancestanceUID"]

        self.download_series(
            patient_id, study_uid, series_uid, folder, modifier_callback
        )

        return folder




