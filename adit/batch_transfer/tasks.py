from datetime import timedelta
import redis
from celery import shared_task, chord
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils import timezone
from django.template.defaultfilters import pluralize
from adit.core.models import TransferTask
from adit.core.tasks import on_job_failed, transfer_dicoms
from adit.core.utils.scheduler import Scheduler
from adit.core.utils.redis_lru import redis_lru
from adit.core.utils.mail import send_job_finished_mail
from .models import BatchTransferSettings, BatchTransferJob, BatchTransferRequest
from .errors import NoStudiesFoundError

logger = get_task_logger(__name__)


@shared_task(ignore_result=True)
def batch_transfer(job_id):
    logger.info("Prepare batch transfer job. [Job ID %d]", job_id)

    job = BatchTransferJob.objects.get(id=job_id)

    if job.status != BatchTransferJob.Status.PENDING:
        raise AssertionError(
            f"Invalid batch transfer job status: {job.get_status_display()} "
            f"[Job ID {job.id}]"
        )

    priority = settings.BATCH_TRANSFER_DEFAULT_PRIORITY
    if job.transfer_urgently:
        priority = settings.BATCH_TRANSFER_URGENT_PRIORITY

    transfer_requests = [
        transfer_request.s(request.id).set(priority=priority)
        for request in job.requests.all()
    ]

    chord(transfer_requests)(
        on_job_finished.s(job_id).on_error(on_job_failed.s(job_id=job_id))
    )


# pylint: disable=too-many-locals,too-many-statements
@shared_task(bind=True)
def transfer_request(self, request_id):
    request = BatchTransferRequest.objects.get(id=request_id)
    job = request.job

    logger.info(
        "Processing batch transfer request. [Job ID %d, Request ID %d, RowNumber %d]",
        job.id,
        request.id,
        request.row_number,
    )

    if request.status != BatchTransferRequest.Status.PENDING:
        raise AssertionError(
            "Invalid batch transfer request processing status: "
            f"{request.get_status_display()} "
            f"[Job ID {job.id}, Request ID {request.id}, RowNumber {request.row_number}]"
        )

    if job.status == BatchTransferJob.Status.CANCELING:
        request.status = BatchTransferRequest.Status.CANCELED
        request.end = timezone.now()
        request.save()
        return request.status

    _check_can_run_now(self, request)

    if job.status == BatchTransferJob.Status.PENDING:
        job.status = BatchTransferJob.Status.IN_PROGRESS
        job.start = timezone.now()
        job.save()

    request.status = BatchTransferRequest.Status.IN_PROGRESS
    request.start = timezone.now()
    request.save()

    try:
        connector = job.source.dicomserver.create_connector()

        patient_id = _fetch_patient_id(
            request.patient_id,
            request.patient_name,
            request.patient_birth_date,
            connector,
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
        logger.debug(
            "Found %d %s to transfer. [Job ID %d, Request ID %d, RowNumber %d]",
            study_count,
            study_str,
            job.id,
            request.id,
            request.row_number,
        )

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

            transfer_task = TransferTask.objects.create(
                content_object=request,
                job=job,
                patient_id=patient_id,
                study_uid=study_uid,
                series_uids=series_uids,
                pseudonym=request.pseudonym,
            )

            task_status = transfer_dicoms(transfer_task.id)
            if task_status == TransferTask.Status.SUCCESS:
                has_success = True
            if task_status == TransferTask.Status.FAILURE:
                has_failure = True

        if has_failure and has_success:
            raise ValueError("Some transfer tasks failed")

        if has_failure and not has_success:
            raise ValueError("All transfer tasks failed.")

        request.status = BatchTransferRequest.Status.SUCCESS
        request.message = "All transfers succeeded."

    except NoStudiesFoundError:
        logger.warning(
            (
                "No studies found for batch transfer request. "
                "[Job ID %d, Request ID %d, RowNumber %d]"
            ),
            job.id,
            request.id,
            request.row_number,
        )
        request.status = BatchTransferRequest.Status.WARNING
        request.message = "No studies found to transfer."

    except Exception as err:  # pylint: disable=broad-except
        logger.exception(
            (
                "Error during transferring batch transfer request. "
                "[Job ID %d, Request ID %d, RowNumber %d]"
            ),
            job.id,
            request.id,
            request.row_number,
        )
        request.status = BatchTransferRequest.Status.FAILURE
        request.message = str(err)

    finally:
        request.end = timezone.now()
        request.save()

    return request.status


@shared_task(ignore_result=True)
def on_job_finished(request_status_list, job_id):
    logger.info("Batch transfer job finished. [Job ID %d]", job_id)

    job = BatchTransferJob.objects.get(id=job_id)

    if (
        job.status == BatchTransferJob.Status.CANCELING
        and BatchTransferRequest.Status.CANCELED in request_status_list
    ):
        job.status = BatchTransferJob.Status.CANCELED
        job.save()
        return

    has_success = False
    has_failure = False
    has_warning = False
    for status in request_status_list:
        if status == BatchTransferRequest.Status.SUCCESS:
            has_success = True
        elif status == BatchTransferRequest.Status.WARNING:
            has_warning = True
        elif status == BatchTransferRequest.Status.FAILURE:
            has_failure = True
        else:
            raise AssertionError(
                f"Invalid batch transfer request result status: {status} [Job ID {job.id}]"
            )

    if has_success and has_failure:
        job.status = BatchTransferJob.Status.WARNING
        job.message = "Some requests failed."
    elif has_success and has_warning:
        job.status = BatchTransferJob.Status.WARNING
        job.message = "Some requests have warnings."
    elif has_success:
        job.status = BatchTransferJob.Status.SUCCESS
        job.message = "All requests succeeded."
    elif has_failure:
        job.status = BatchTransferJob.Status.FAILURE
        job.message = "All requests failed."
    elif has_warning:
        job.status = BatchTransferJob.Status.WARNING
        job.message = "All requests have warnings."
    else:
        raise AssertionError(
            f"At least one request must succeed, fail or have a warning. [Job ID {job.id}]"
        )

    job.end = timezone.now()
    job.save()

    send_job_finished_mail(job)


def _check_can_run_now(celery_task, request):
    batch_transfer_settings = BatchTransferSettings.get()

    if not request.job.transfer_urgently:
        scheduler = Scheduler(
            batch_transfer_settings.slot_begin_time,
            batch_transfer_settings.slot_end_time,
        )
        if scheduler.must_be_scheduled():
            raise celery_task.retry(
                eta=scheduler.next_slot(),
                exc=Warning(
                    f"Batch transfer outside of time slot. "
                    f"[Job ID {request.job.id}, Request ID {request.id}, RowNumber {request.row_number}]"
                ),
            )

    if batch_transfer_settings.suspended:
        raise celery_task.retry(
            eta=timezone.now() + timedelta(minutes=60),
            exc=Warning(
                "Batch transfer suspended. "
                f"[Job ID {request.job.id}, Request ID {request.id}, RowNumber {request.row_number}]"
            ),
        )


@redis_lru(capacity=10000, slicer=slice(3))
def _fetch_patient_id(patient_id, patient_name, birth_date, connector):
    """Fetch the patient for this request.

    Raises an error if there is no patient or there are multiple patients for this request.
    """
    patients = connector.find_patients(
        {
            "PatientID": patient_id,
            "PatientName": patient_name,
            "PatientBirthDate": birth_date,
        }
    )

    if len(patients) == 0:
        raise ValueError("No patients found.")
    if len(patients) > 1:
        raise ValueError("Multiple patients found.")

    return patients[0]["PatientID"]


_fetch_patient_id.init(redis.Redis.from_url(settings.REDIS_URL))
