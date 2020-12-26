from celery import shared_task, chord
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils import timezone
from django.template.defaultfilters import pluralize
from adit.core.utils.transfer_util import TransferUtil
from adit.core.utils.mail import send_job_finished_mail
from adit.core.utils.task_utils import (
    prepare_dicom_job,
    prepare_dicom_task,
    finish_dicom_job,
    handle_job_failure,
    fetch_patient_id_cached,
)
from .models import (
    BatchTransferSettings,
    BatchTransferJob,
    BatchTransferRequest,
    BatchTransferTask,
)
from .errors import NoStudiesFoundError

logger = get_task_logger(__name__)


@shared_task(ignore_result=True)
@prepare_dicom_job(BatchTransferJob, logger)
def batch_transfer(transfer_job: BatchTransferJob):
    priority = settings.BATCH_TRANSFER_DEFAULT_PRIORITY
    if transfer_job.urgent:
        priority = settings.BATCH_TRANSFER_URGENT_PRIORITY

    transfer_requests = [
        transfer_request.s(request.id).set(priority=priority)
        for request in transfer_job.requests.all()
    ]

    chord(transfer_requests)(
        on_job_finished.s(transfer_job.id).on_error(
            on_job_failed.s(job_id=transfer_job.id)
        )
    )


# pylint: disable=too-many-locals
@shared_task(bind=True)
@prepare_dicom_task(BatchTransferRequest, BatchTransferSettings, logger)
def transfer_request(request: BatchTransferRequest):
    job = request.job

    request.status = BatchTransferRequest.Status.IN_PROGRESS
    request.start = timezone.now()
    request.save()

    try:
        connector = job.source.dicomserver.create_connector()

        patient_id = fetch_patient_id_cached(
            connector,
            request.patient_id,
            request.patient_name,
            request.patient_birth_date,
        )
        studies = connector.find_studies(
            {
                "PatientID": patient_id,
                "AccessionNumber": request.accession_number,
                "StudyDate": request.study_date,
                "ModalitiesInStudy": request.modality,
                "StudyInstanceUID": "",
            }
        )

        study_count = len(studies)

        if study_count == 0:
            raise NoStudiesFoundError()

        study_str = "stud{}".format(pluralize(study_count, "y, ies"))
        logger.debug("Found %d %s to transfer for %s.", study_count, study_str, request)

        has_success = False
        has_failure = False
        for study in studies:
            study_uid = study["StudyInstanceUID"]

            series_list = connector.find_series(
                {
                    "PatientID": patient_id,
                    "StudyInstanceUID": study_uid,
                    "Modality": request.modality,
                    "SeriesInstanceUID": "",
                }
            )
            series_uids = [series["SeriesInstanceUID"] for series in series_list]

            transfer_task = BatchTransferTask.objects.create(
                content_object=request,
                job=job,
                patient_id=patient_id,
                study_uid=study_uid,
                series_uids=series_uids,
                pseudonym=request.pseudonym,
            )

            transfer_util = TransferUtil(transfer_task)
            task_status = transfer_util.start_transfer()

            if task_status == BatchTransferTask.Status.SUCCESS:
                has_success = True
            if task_status == BatchTransferTask.Status.FAILURE:
                has_failure = True

        if has_failure and has_success:
            raise ValueError("Some transfer tasks failed")

        if has_failure and not has_success:
            raise ValueError("All transfer tasks failed.")

        request.status = BatchTransferRequest.Status.SUCCESS
        request.message = "All transfers succeeded."

    except NoStudiesFoundError:
        logger.warning("No studies found for %s. ", request)
        request.status = BatchTransferRequest.Status.WARNING
        request.message = "No studies found to transfer."

    except Exception as err:  # pylint: disable=broad-except
        logger.exception("Error during %s.", request)
        request.status = BatchTransferRequest.Status.FAILURE
        request.message = str(err)

    finally:
        request.end = timezone.now()
        request.save()

    return request.status


@shared_task(ignore_result=True)
@finish_dicom_job(BatchTransferJob, logger)
def on_job_finished(transfer_job: BatchTransferJob):
    send_job_finished_mail(transfer_job)


@shared_task
@handle_job_failure(BatchTransferJob, logger)
def on_job_failed(transfer_job: BatchTransferJob):  # pylint: disable=unused-argument
    pass
