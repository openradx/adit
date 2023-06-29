from adrf.views import sync_to_async
from rest_framework.exceptions import NotFound

from adit.core.models import DicomServer
from adit.core.utils.dicom_connector import DicomConnector
from adit.core.utils.dicom_utils import adit_dict_to_dicom_json, format_datetime_attributes


async def qido_find(source_server: DicomServer, request_query: dict, level: str):
    query = await create_query(request_query)
    connector = DicomConnector(source_server)
    if level == "STUDY":
        results = await sync_to_async(connector.find_studies)(query)
    elif level == "SERIES":
        results = await sync_to_async(connector.find_series)(query)
    else:
        raise NotFound("Supported levels are 'STUDY' and 'SERIES'")

    if len(results) <= 0:
        raise NotFound("No query results found.")

    results = await sync_to_async(adit_dict_to_dicom_json)(results)
    return results


async def create_query(request_query: dict) -> dict:
    query = {
        "StudyInstanceUID": "",
        "SeriesInstanceUID": "",
        "PatientID": "",
        "PatientName": "",
        "PatientBirthDate": "",
        "PatientSex": "",
        "AccessionNumber": "",
        "StudyDate": "",
        "StudyTime": "",
        "ModalitiesInStudy": "",
        "Modality": "",
        "NumberOfStudyRelatedInstances": "",
        "NumberOfSeriesRelatedInstances": "",
        "SOPInstaceUID": "",
        "StudyDescription": "",
        "SeriesDescription": "",
        "SeriesNumber": "",
    }
    for attribute, value in request_query.items():
        query[attribute] = value
    query = await sync_to_async(format_datetime_attributes)([query])
    return query[0]
