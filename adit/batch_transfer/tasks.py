from celery import shared_task, chord
from django.conf import settings
from adit.main.models import TransferTask
from adit.main.tasks import transfer_dicoms
from adit.main.utils.cache import LRUCache
from adit.main.utils.scheduler import Scheduler
from .models import AppSettings, BatchTransferJob, BatchTransferRequest

patient_cache = LRUCache(settings.BATCH_PATIENT_CACHE_SIZE)


@shared_task(ignore_result=True)
def batch_transfer(job_id):
    job = BatchTransferJob.objects.get(id=job_id)

    if job.status != BatchTransferJob.Status.PENDING:
        raise AssertionError(f"Invalid job status: {job.get_status_display()}")

    transfer_requests = [
        transfer_request.s(request.id) for request in job.requests.all()
    ]

    chord(transfer_requests)(update_job_status.s(job_id))


@shared_task(bind=True)
def transfer_request(self, request_id):
    request = BatchTransferRequest.objects.get(id=request_id)

    if request.status != BatchTransferRequest.Status.PENDING:
        raise AssertionError(
            f"Invalid transfer job status: {request.get_status_display()}"
        )

    job = request.job

    if job.status == BatchTransferJob.Status.CANCELING:
        request.status = BatchTransferRequest.Status.CANCELED
        request.save()
        return request.status

    app_settings = AppSettings.load()
    scheduler = Scheduler(
        app_settings.batch_slot_begin_time,
        app_settings.batch_slot_end_time,
        app_settings.batch_transfer_suspended,
    )

    if scheduler.must_be_scheduled():
        raise self.retry(eta=scheduler.next_slot())

    if job.status == BatchTransferJob.Status.PENDING:
        job.status = BatchTransferJob.Status.IN_PROGRESS
        job.save()

    request.status = BatchTransferRequest.Status.IN_PROGRESS
    request.save()

    try:
        connector = job.source.create_connector()

        patient_id = _fetch_patient(request, connector)["PatientID"]
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
        request.save()

    except Exception as err:  # pylint: disable=broad-except
        request.status = BatchTransferRequest.Status.FAILURE
        request.message = str(err)
        request.save()

    return request.status


@shared_task(ignore_result=True)
def update_job_status(request_status_list, job_id):
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


def _fetch_patient(request, connector):
    """Fetch the patient for this request.

    Raises an error if there is no patient or there are multiple patients for this request.
    """
    patient_id = request.patient_id
    patient_name = request.patient_name
    patient_birth_date = request.patient_birth_date

    patient_key = f"{patient_id}__{patient_name}__{patient_birth_date}"
    patient = patient_cache.get(patient_key)
    if patient:
        return patient

    patients = connector.find_patients(patient_id, patient_name, patient_birth_date)
    if len(patients) == 0:
        raise ValueError("No patients found.")
    if len(patients) > 1:
        raise ValueError("Multiple patients found.")

    patient = patients[0]
    patient_id = patient["PatientID"]
    patient_name = patient["PatientName"]
    patient_birth_date = patient["PatientBirthDate"]

    patient_key = f"{patient_id}__{patient_name}__{patient_birth_date}"
    patient_cache.set(patient_key, patient)

    return patient
