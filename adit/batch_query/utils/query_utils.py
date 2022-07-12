import logging
from typing import Any, Dict, List, Optional
from django.utils import timezone
from django.template.defaultfilters import pluralize
from adit.core.utils.dicom_connector import DicomConnector
from adit.core.utils.task_utils import hijack_logger, store_log_in_task
from ..models import BatchQueryTask, BatchQueryResult

logger = logging.getLogger(__name__)

DICOM_DATE_FORMAT = "%Y%m%d"


def execute_query(query_task: BatchQueryTask) -> BatchQueryTask.Status:
    if query_task.status == BatchQueryTask.Status.CANCELED:
        return query_task.status

    query_task.status = BatchQueryTask.Status.IN_PROGRESS
    query_task.start = timezone.now()
    query_task.save()

    logger.info("Started %s.", query_task)

    handler, stream = hijack_logger(logger)

    connector: DicomConnector = _create_source_connector(query_task)

    try:
        patients = _fetch_patients(connector, query_task)

        if len(patients) == 0:
            query_task.status = BatchQueryTask.Status.WARNING
            query_task.message = "Patient not found."
        else:
            all_studies = []  # a list of study lists (per patient)
            for patient in patients:
                studies = _query_studies(connector, patient["PatientID"], query_task)
                if studies:
                    if query_task.series_description:
                        for study in studies:
                            series = _query_series(connector, study, query_task)
                            all_studies.append(series)
                    else:
                        all_studies.append(studies)

            if len(all_studies) == 0:
                query_task.status = BatchQueryTask.Status.WARNING
                query_task.message = "No studies for patient found."
            else:
                all_studies_flattened = [
                    study for studies in all_studies for study in studies
                ]
                results = _save_results(query_task, all_studies_flattened)

                num = len(results)
                if query_task.series_description:
                    study_count = f"{num} series"
                else:
                    study_count = f"{num} stud{pluralize(num, 'y,ies')}"

                if len(all_studies) == 1:  # Only studies of one patient found
                    query_task.status = BatchQueryTask.Status.SUCCESS
                    query_task.message = f"{study_count} found."
                else:  # Studies of multiple patients found
                    query_task.status = BatchQueryTask.Status.WARNING
                    query_task.message = (
                        f"Multiple patients found with overall {study_count}."
                    )
    except Exception as err:  # pylint: disable=broad-except
        logger.exception("Error during %s", query_task)
        query_task.status = BatchQueryTask.Status.FAILURE
        query_task.message = str(err)
    finally:
        store_log_in_task(logger, handler, stream, query_task)
        query_task.end = timezone.now()
        query_task.save()

    return query_task.status


def _create_source_connector(query_task: BatchQueryTask) -> DicomConnector:
    # An own function to easily mock the source connector in test_transfer_utils.py
    return DicomConnector(query_task.job.source.dicomserver)


def _fetch_patients(
    connector: DicomConnector, query_task: BatchQueryTask
) -> Optional[Dict[str, Any]]:
    return connector.find_patients(
        {
            "PatientID": query_task.patient_id,
            "PatientName": query_task.patient_name,
            "PatientBirthDate": query_task.patient_birth_date,
        }
    )


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
            "PatientName": query_task.patient_name,
            "PatientBirthDate": query_task.patient_birth_date,
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


def _query_series(
    connector: DicomConnector, study: List[Dict[str, Any]], query_task: BatchQueryTask
) -> List[Dict[str, Any]]:

    found_series = connector.find_series(
        {
            "PatientID": study["PatientID"],
            "StudyInstanceUID": study["StudyInstanceUID"],
            "SeriesInstanceUID": "",
            "SeriesDescription": query_task.series_description,
        }
    )

    for series in found_series:
        series.update(study)

    return found_series


def _save_results(
    query_task: BatchQueryTask, studies: List[Dict[str, Any]]
) -> List[BatchQueryResult]:
    results = []
    for study in studies:
        series_uid = ""
        if "SeriesInstanceUID" in study:
            series_uid = study["SeriesInstanceUID"]
        series_description = ""
        if "SeriesDescription" in study:
            series_description = study["SeriesDescription"]

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
            pseudonym=query_task.pseudonym,
            series_uid=series_uid,
            series_description=series_description,
        )
        results.append(result)

    BatchQueryResult.objects.bulk_create(results)

    return results
