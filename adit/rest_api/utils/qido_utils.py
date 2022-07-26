from adit.core.utils.dicom_connector import DicomConnector

def execute_qido(dicom_task):   
    connector = DicomConnector(dicom_task.job.source)
    
    query = _create_query(dicom_task)
    
    StudyInstance = connector.find_studies(query)

    return StudyInstance


def _create_query(dicom_task):
    query = {
        "StudyInstanceUID": dicom_task.study_uid,
        "SeriesInstanceUID": dicom_task.series_uid,

        "PatientID": "",
        "PatientName": "",
        "PatientBithDate": "",
        "AccessionNumber": "",
        "StudyDate": "",
        "ModalitiesInStudy": "",
        "NumberOfStudyRelatedInstances": "",
        "NumberOfSeriesRelatedInstances": "",
        "SOPInstaceUID": "",
        "SeriesDescription": "",
    }
    return query