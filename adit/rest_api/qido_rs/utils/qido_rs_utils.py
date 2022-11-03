import json

from django.utils import timezone

from ...utils.dicom_web_utils import DicomWebApi
from adit.core.utils.dicom_connector import DicomConnector
from adit.xnat_support.utils.xnat_connector import XnatConnector
from adit.core.utils.dicom_utils import format_datetime_attributes
from adit.core.utils.task_utils import hijack_logger, store_log_in_task


from celery import Task as CeleryTask
from celery.utils.log import get_task_logger

from ..models import DicomQidoJob, DicomQidoTask, DicomQidoResult

from pydicom.dataset import Dataset


logger = get_task_logger(__name__)


def execute_qido(
    dicom_qido_task: DicomQidoTask, celery_task: CeleryTask
) -> DicomQidoTask.Status:
    logger.debug("hi0")
    if dicom_qido_task.status == DicomQidoTask.Status.CANCELED:
        return dicom_qido_task.status

    if dicom_qido_task.status != DicomQidoTask.Status.PENDING:
        raise AssertionError(
            f"Invalid status {dicom_qido_task.status} of {dicom_qido_task}"
        )

    dicom_qido_task.status = DicomQidoTask.Status.IN_PROGRESS
    dicom_qido_task.start = timezone.now()
    dicom_qido_task.save()

    logger.info("Started %s.", dicom_qido_task)

    handler, stream = hijack_logger(logger)

    dicom_qido_job: DicomQidoJob = dicom_qido_task.job

    try:
        if not dicom_qido_job.source.source_active:
            raise ValueError(
                f"Source DICOM node not active: {dicom_qido_job.source.name}"
            )

        _c_find_to_result(dicom_qido_task)

        dicom_qido_task.status = DicomQidoTask.Status.SUCCESS
        dicom_qido_task.message = "Query task completed successfully."
        dicom_qido_task.end = timezone.now()

    except Exception as err:  # pylint: disable=broad-except
        logger.exception("Unrecoverable failure occurred in %s.", dicom_qido_task)
        dicom_qido_task.status = DicomQidoTask.Status.FAILURE
        dicom_qido_task.message = str(err)
        dicom_qido_task.end = timezone.now()

    finally:
        store_log_in_task(logger, handler, stream, dicom_qido_task)
        dicom_qido_task.save()

    return dicom_qido_task.status


def _c_find_to_result(dicom_qido_task: DicomQidoTask) -> None:
    if dicom_qido_task.job.source.dicomserver.xnat_rest_source:
        connector = XnatConnector(dicom_qido_task.job.source.dicomserver)
    else:
        connector = DicomConnector(dicom_qido_task.job.source.dicomserver)
    
    dicom_web_api = DicomWebApi(connector)

    query = _create_query(dicom_qido_task)

    if dicom_qido_task.job.level == "STUDY":
        c_find_result = dicom_web_api.qido_find_studies(query)
    elif dicom_qido_task.job.level == "SERIES":
        c_find_result = dicom_web_api.qido_find_series(query)

    if len(c_find_result) <= 0:
        raise ValueError("No query results found.")

    result = DicomQidoResult(
        job=dicom_qido_task.job,
        query_results=json.dumps(c_find_result, default=str),
    )
    result.save()


def _create_query(dicom_task: DicomQidoTask) -> dict:
    query = {
        "StudyInstanceUID": dicom_task.study_uid,
        "SeriesInstanceUID": dicom_task.series_uid,
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

    request_query = eval(dicom_task.query)
    for attribute, value in request_query.items():
        query[attribute] = value

    query = format_datetime_attributes([query])[0]

    return query
