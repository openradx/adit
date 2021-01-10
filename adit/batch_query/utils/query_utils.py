import logging
from typing import Any, Dict, List, Optional
from django.utils import timezone
from django.template.defaultfilters import pluralize
from adit.core.utils.dicom_connector import DicomConnector
from ..models import BatchQueryTask, BatchQueryResult

logger = logging.getLogger(__name__)

DICOM_DATE_FORMAT = "%Y%m%d"


def execute_query(query_task: BatchQueryTask) -> BatchQueryTask.Status:
    if query_task.status == BatchQueryTask.Status.CANCELED:
        return query_task.status

    query_task.status = BatchQueryTask.Status.IN_PROGRESS
    query_task.start = timezone.now()
    query_task.save()

    connector: DicomConnector = _create_source_connector(query_task)

    try:
        patient = _fetch_patient(connector, query_task)

        if not patient:
            query_task.status = BatchQueryTask.Status.WARNING
            query_task.message = "Patient not found."
        else:
            studies = _query_studies(connector, patient["PatientID"], query_task)

            if not studies:
                query_task.status = BatchQueryTask.Status.WARNING
                query_task.message = "No studies found."
            else:
                results = _save_results(query_task, studies)
                query_task.status = BatchQueryTask.Status.SUCCESS
                num = len(results)
                query_task.message = f"{num} stud{pluralize(num, 'y,ies')} found."

    except Exception as err:  # pylint: disable=broad-except
        logger.exception("Error during %s", query_task)
        query_task.status = BatchQueryTask.Status.FAILURE
        query_task.message = str(err)
    finally:
        query_task.end = timezone.now()
        query_task.save()

    return query_task.status


def _create_source_connector(query_task: BatchQueryTask) -> DicomConnector:
    # An own function to easily mock the source connector in test_transfer_utils.py
    return query_task.job.source.dicomserver.create_connector()


def _fetch_patient(
    connector: DicomConnector, query_task: BatchQueryTask
) -> Optional[Dict[str, Any]]:
    patients = connector.find_patients(
        {
            "PatientID": query_task.patient_id,
            "PatientName": query_task.patient_name,
            "PatientBirthDate": query_task.patient_birth_date,
        }
    )

    if len(patients) > 1:
        raise ValueError("Multiple patients found.")

    if len(patients) == 1:
        return patients[0]

    return None


def _query_studies(
    connector: DicomConnector, patient_id: str, query_task: BatchQueryTask
) -> List[Dict[str, Any]]:
    study_date = ""
    if query_task.study_date_start:
        if not query_task.study_date_end:
            study_date = query_task.study_date_start.strftime(DICOM_DATE_FORMAT) + "-"
        elif query_task.study_date_start == query_task.study_date_end:
            study_date = query_task.study_date_start.strftime(DICOM_DATE_FORMAT)
        else:
            study_date = (
                query_task.study_date_start.strftime(DICOM_DATE_FORMAT)
                + "-"
                + query_task.study_date_end.strftime(DICOM_DATE_FORMAT)
            )
    elif query_task.study_date_end:
        study_date = "-" + query_task.study_date_end.strftime(DICOM_DATE_FORMAT)

    studies = connector.find_studies(
        {
            "PatientID": patient_id,
            "StudyInstanceUID": "",
            "AccessionNumber": query_task.accession_number,
            "StudyDate": study_date,
            "StudyTime": "",
            "StudyDescription": "",
            "ModalitiesInStudy": query_task.modalities,
            "NumberOfStudyRelatedInstances": "",
        }
    )

    return studies


def _save_results(
    query_task: BatchQueryTask, studies: List[Dict[str, Any]]
) -> List[BatchQueryResult]:
    results = []
    for study in studies:
        result = BatchQueryResult(
            job=query_task.job,
            query=query_task,
            patient_id=study["PatientID"],
            patient_name=study["PatientName"],
            patient_birth_date=study["PatientBirthDate"],
            study_uid=study["StudyInstanceUID"],
            accession_number=study["AccessionNumber"],
            study_date=study["StudyDate"],
            study_time=study["StudyTime"],
            study_description=study["StudyDescription"],
            modalities=study["ModalitiesInStudy"],
            image_count=study["NumberOfStudyRelatedInstances"],
        )
        results.append(result)

    BatchQueryResult.objects.bulk_create(results)

    return results