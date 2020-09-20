from datetime import timedelta
import redis
from celery import shared_task, chord
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from django.contrib.humanize.templatetags.humanize import naturaltime
from adit.main.models import TransferTask
from adit.main.tasks import transfer_dicoms
from adit.main.utils.scheduler import Scheduler
from adit.main.utils.redis_lru import redis_lru
from adit.main.utils.mail import send_mail_to_user, send_mail_to_admins
from .models import AppSettings, BatchTransferJob, BatchTransferRequest

logger = get_task_logger("adit." + __name__)


@shared_task(ignore_result=True)
def batch_transfer(job_id):
    job = BatchTransferJob.objects.get(id=job_id)

    if job.status != BatchTransferJob.Status.PENDING:
        raise AssertionError(f"Invalid job status: {job.get_status_display()}")

    transfer_requests = [
        transfer_request.s(request.id) for request in job.requests.all()
    ]

    chord(transfer_requests)(
        on_job_finished.s(job_id).on_error(on_job_failed.s(job_id=job_id))
    )


@shared_task(bind=True)
def transfer_request(self, row_key):
    request = BatchTransferRequest.objects.get(id=row_key)

    # TODO remove
    # print("+++++++++++")
    # print(request.patient_id)
    # if request.patient_id == "10007":
    #     raise Exception("A test exception")

    if request.status != BatchTransferRequest.Status.PENDING:
        raise AssertionError(
            f"Invalid transfer job status: {request.get_status_display()}"
        )

    job = request.job

    if job.status == BatchTransferJob.Status.CANCELING:
        request.status = BatchTransferRequest.Status.CANCELED
        request.stopped_at = timezone.now()
        request.save()
        return request.status

    app_settings = AppSettings.load()

    scheduler = Scheduler(
        app_settings.batch_slot_begin_time, app_settings.batch_slot_end_time
    )
    if scheduler.must_be_scheduled():
        eta = scheduler.next_slot()
        raise self.retry(
            eta=eta, exc=Warning(f"Not in batch slot. Scheduled in {naturaltime(eta)}.")
        )

    if app_settings.batch_transfer_suspended:
        eta = timezone.now + timedelta(minutes=5)
        raise self.retry(
            eta=eta,
            exc=Warning(f"Batch transfer suspended. Retrying in {naturaltime(eta)}."),
        )

    if job.status == BatchTransferJob.Status.PENDING:
        job.status = BatchTransferJob.Status.IN_PROGRESS
        job.started_at = timezone.now()
        job.save()

    request.status = BatchTransferRequest.Status.IN_PROGRESS
    request.started_at = timezone.now()
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
            patient_id,
            accession_number=request.accession_number,
            study_date=request.study_date,
            modality=request.modality,
        )

        if len(studies) == 0:
            raise ValueError("No studies found to transfer.")

        has_success = False
        has_failure = False
        for study in studies:
            transfer_task = TransferTask.objects.create(
                content_object=request,
                job=job,
                patient_id=patient_id,
                study_uid=study["StudyInstanceUID"],
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

    except Exception as err:  # pylint: disable=broad-except
        logger.exception(
            (
                "Error during transferring batch request "
                "(Job ID %d, Request ID %d, Row Key %s)."
            ),
            job.id,
            request.id,
            request.row_key,
        )
        request.status = BatchTransferRequest.Status.FAILURE
        request.message = str(err)
    finally:
        request.stopped_at = timezone.now()
        request.save()

    return request.status


@shared_task(ignore_result=True)
def on_job_finished(request_status_list, job_id):
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
    for status in request_status_list:
        if status == BatchTransferRequest.Status.SUCCESS:
            has_success = True
        elif status == BatchTransferRequest.Status.FAILURE:
            has_failure = True
        else:
            raise AssertionError("Invalid request status.")

    if has_success and has_failure:
        job.status = BatchTransferJob.Status.WARNING
        job.message = "Some requests failed."
    elif has_success:
        job.status = BatchTransferJob.Status.SUCCESS
        job.message = "All requests succeeded."
    elif has_failure:
        job.status = BatchTransferJob.Status.FAILURE
        job.message = "All requests failed."
    else:
        raise AssertionError("Invalid request status.")

    job.stopped_at = timezone.now()
    job.save()

    html_content = render_to_string(
        "batch_transfer/mail/batch_transfer_finished.html",
        {"BASE_URL": settings.BASE_URL, "job": job},
    )
    send_mail_to_user("Batch transfer job finished", html_content, job.created_by)


# The Celery documentation is wrong about the provided parameters and when
# the callback is called. This function definition seems to work however.
# See https://github.com/celery/celery/issues/3709
@shared_task
def on_job_failed(*args, **kwargs):
    celery_task_id = args[0]
    job_id = kwargs["job_id"]

    job = BatchTransferJob.objects.get(id=job_id)

    job.status = BatchTransferJob.Status.FAILURE
    job.message = "Job failed unexpectedly."
    job.save()

    subject = "Batch transfer job failed"
    html_content = render_to_string(
        "batch_transfer/mail/batch_transfer_failed.html",
        {"BASE_URL": settings.BASE_URL, "job": job, "celery_task_id": celery_task_id},
    )
    send_mail_to_admins(subject, html_content)
    send_mail_to_user(subject, html_content, job.created_by)


@redis_lru(capacity=10000, slicer=slice(3))
def _fetch_patient_id(patient_id, patient_name, patient_birth_date, connector):
    """Fetch the patient for this request.

    Raises an error if there is no patient or there are multiple patients for this request.
    """
    patients = connector.find_patients(patient_id, patient_name, patient_birth_date)

    if len(patients) == 0:
        raise ValueError("No patients found.")
    if len(patients) > 1:
        raise ValueError("Multiple patients found.")

    return patients[0]["PatientID"]


_fetch_patient_id.init(redis.Redis.from_url(settings.REDIS_URL))
