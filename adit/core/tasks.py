import io
import logging
from pathlib import Path
from datetime import datetime
import tempfile
import subprocess
from functools import partial
from celery import shared_task
from celery.utils.log import get_task_logger
from dicognito.anonymizer import Anonymizer
from django.utils import timezone
from .utils.dicom_connector import DicomConnector
from .utils.sanitize import sanitize_dirname
from .utils.mail import send_job_failed_mail, send_mail_to_admins
from .models import DicomNode, DicomFolder, TransferJob, TransferTask

logger = get_task_logger(__name__)


@shared_task(ignore_result=True)
def check_disk_space():
    folders = DicomFolder.objects.filter(destination_active=True)
    for folder in folders:
        size = int(
            subprocess.check_output(["du", "-sm", folder.path])
            .split()[0]
            .decode("utf-8")
        )
        if folder.warn_size is not None and size > folder.warn_size:
            quota = "?"
            if folder.quota is not None:
                quota = folder.quota
            msg = (
                f"Low disk space of destination folder: {folder.name}\n"
                f"{size} MB of {quota} MB used."
            )
            logger.warning(msg)
            send_mail_to_admins("Warning, low disk space!", msg)


# The Celery documentation is wrong about the provided parameters and when
# the callback is called. This function definition seems to work however.
# See https://github.com/celery/celery/issues/3709
@shared_task
def on_job_failed(*args, **kwargs):
    celery_task_id = args[0]
    job_id = kwargs["job_id"]

    logger.error("Transfer job failed unexpectedly. [Job ID %d]", job_id)

    job = TransferJob.objects.get(id=job_id)

    job.status = TransferJob.Status.FAILURE
    job.message = "Transfer job failed unexpectedly."
    job.save()

    send_job_failed_mail(job, celery_task_id)


@shared_task
def transfer_dicoms(task_id):
    task = TransferTask.objects.get(id=task_id)
    job = task.job

    if task.status != TransferTask.Status.PENDING:
        raise AssertionError(
            f"Invalid transfer task status {task.status} "
            f"[Job ID {job.id}, Task ID {task.id}]."
        )

    task.status = TransferTask.Status.IN_PROGRESS
    task.start = timezone.now()
    task.save()

    logger.debug(
        "Transfer task started. [Job ID %d, Task ID %d, Source %s, Destination %s]",
        job.id,
        task.id,
        job.source.name,
        job.destination.name,
    )

    handler, stream = _setup_logger()

    try:
        if not job.source.source_active:
            raise ValueError(f"Source DICOM node not active: {job.source.name}")

        if not job.destination.destination_active:
            raise ValueError(
                f"Destination DICOM node not active: {job.destination.name}"
            )

        if job.destination.node_type == DicomNode.NodeType.SERVER:
            _transfer_to_server(task)
        elif job.destination.node_type == DicomNode.NodeType.FOLDER:
            if job.archive_password:
                _transfer_to_archive(task)
            else:
                _transfer_to_folder(task)
        else:
            raise AssertionError(f"Invalid node type: {job.destination}")

        task.status = TransferTask.Status.SUCCESS
        task.message = "Transfer task completed successfully."

    except Exception as err:  # pylint: disable=broad-except
        logger.exception(
            "Error during transfer task [Job ID %d, Task ID %d].",
            job.id,
            task.id,
        )
        task.status = TransferTask.Status.FAILURE
        task.message = str(err)
    finally:
        _save_log_to_task(handler, stream, task)

        task.end = timezone.now()
        task.save()

    return task.status


def _setup_logger():
    """Intercept all logger messages to save them later to the task.

    This only works when the logger is fetched by Celery get_task_logger.
    """
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.parent.addHandler(handler)

    return handler, stream


def _save_log_to_task(handler, stream, task):
    handler.flush()
    if task.log:
        task.log += "\n" + stream.getvalue()
    else:
        task.log = stream.getvalue()
    stream.close()
    logger.parent.removeHandler(handler)


def _transfer_to_server(transfer_task: TransferTask):
    job = transfer_task.job
    source_connector = job.source.dicomserver.create_connector()
    dest_connector = job.destination.dicomserver.create_connector()

    with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
        patient_folder = _download_dicoms(source_connector, transfer_task, Path(tmpdir))
        dest_connector.upload_folder(patient_folder)


def _transfer_to_archive(transfer_task: TransferTask):
    job = transfer_task.job
    source_connector = job.source.dicomserver.create_connector()
    archive_folder = Path(job.destination.dicomfolder.path)
    archive_password = job.archive_password

    archive_name = f"{_create_destination_name(job)}.7z"
    archive_path = archive_folder / archive_name

    if not archive_path.is_file():
        _create_archive(archive_path, archive_password, job.id)

    with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
        patient_folder = _download_dicoms(source_connector, transfer_task, Path(tmpdir))
        _add_to_archive(archive_path, archive_password, patient_folder)


def _transfer_to_folder(transfer_task: TransferTask):
    job = transfer_task.job
    source_connector = job.source.dicomserver.create_connector()

    dicom_folder = Path(job.destination.dicomfolder.path)
    download_folder = dicom_folder / _create_destination_name(job)

    _download_dicoms(source_connector, transfer_task, download_folder)


def _download_dicoms(
    connector: DicomConnector, transfer_task: TransferTask, download_folder: Path
):
    pseudonym = transfer_task.pseudonym
    if pseudonym:
        patient_folder = download_folder / sanitize_dirname(pseudonym)
    else:
        pseudonym = None
        patient_folder = download_folder / sanitize_dirname(transfer_task.patient_id)

    # Check if the Study Instance UID is correct and fetch some parameters to create
    # the study folder.
    studies = connector.find_studies(
        {
            "PatientID": transfer_task.patient_id,
            "StudyInstanceUID": transfer_task.study_uid,
            "StudyDate": "",
            "StudyTime": "",
            "ModalitiesInStudy": "",
        }
    )
    if len(studies) == 0:
        raise AssertionError(
            f"No study found with Study Instance UID {transfer_task.study_uid}. "
            f"[Job ID {transfer_task.job.id}, Task ID {transfer_task.id}]"
        )
    if len(studies) > 1:
        raise AssertionError(
            f"Multiple studies found with Study Instance UID {transfer_task.study_uid}. "
            f"[Job ID {transfer_task.job.id}, Task ID {transfer_task.id}]"
        )
    study = studies[0]
    study_date = study["StudyDate"]
    study_time = study["StudyTime"]
    modalities = study["ModalitiesInStudy"]

    # If some series are explicitly chosen then check if their Series Instance UIDs
    # are correct and only use their modalities for the name of the study folder.
    if transfer_task.series_uids:
        modalities = set()
        series_list = connector.find_series(
            {
                "PatientID": transfer_task.patient_id,
                "StudyInstanceUID": transfer_task.study_uid,
                "SeriesInstanceUID": "",
                "Modality": "",
            }
        )
        for series_uid in transfer_task.series_uids:
            found_series = None
            for series in series_list:
                if series["SeriesInstanceUID"] == series_uid:
                    found_series = series

            if not found_series:
                raise AssertionError(
                    f"No series found with Series Instance UID {series_uid}. "
                    f"[Job ID {transfer_task.job.id}, Task ID {transfer_task.id}]"
                )

            modalities.add(found_series["Modality"])
    modalities = ",".join(modalities)

    study_folder = patient_folder / f"{study_date}-{study_time}-{modalities}"
    study_folder.mkdir(parents=True, exist_ok=True)

    anonymizer = Anonymizer()
    modifier_callback = partial(
        _modify_dataset,
        anonymizer,
        pseudonym,
        transfer_task.job.trial_protocol_id,
        transfer_task.job.trial_protocol_name,
    )

    if transfer_task.series_uids:
        # Download specific series of a study only.
        _download_series(
            connector, study, transfer_task.series_uids, study_folder, modifier_callback
        )
    else:
        # Download the whole study.
        _download_study(connector, study, study_folder, modifier_callback)

    return patient_folder


def _download_study(connector: DicomConnector, study, study_folder, modifier_callback):
    connector.download_study(
        study["PatientID"],
        study["StudyInstanceUID"],
        study_folder,
        modifier_callback=modifier_callback,
    )


def _download_series(
    connector: DicomConnector, study, series_uids, study_folder, modifier_callback
):
    for series_uid in series_uids:
        series_list = connector.find_series(
            {
                "PatientID": study["PatientID"],
                "StudyInstanceUID": study["StudyInstanceUID"],
                "SeriesInstanceUID": series_uid,
                "SeriesDescription": "",
            }
        )
        if len(series_list) == 0:
            raise AssertionError(
                f"No series found with Series Instance UID: {series_uid}"
            )
        if len(series_list) > 1:
            raise AssertionError(
                f"Multiple series found with Series Instance UID {series_uid}."
            )
        series = series_list[0]
        series_folder_name = sanitize_dirname(series["SeriesDescription"])
        series_folder = study_folder / series_folder_name

        connector.download_series(
            series["PatientID"],
            series["StudyInstanceUID"],
            series["SeriesInstanceUID"],
            series_folder,
            modifier_callback,
        )


def _modify_dataset(anonymizer, pseudonym, trial_protocol_id, trial_protocol_name, ds):
    """Optionally pseudonymize an incoming dataset with the given pseudonym
    and add the trial ID and name to the DICOM header if specified."""
    if pseudonym:
        anonymizer.anonymize(ds)
        ds.PatientID = pseudonym
        ds.PatientName = pseudonym

    if trial_protocol_id:
        ds.ClinicalTrialProtocolID = trial_protocol_id

    if trial_protocol_name:
        ds.ClinicalTrialProtocolName = trial_protocol_name


def _create_archive(archive_path: Path, archive_password: str, job_id: str):
    """Create a new archive with just an INDEX.txt file in it."""
    if Path(archive_path).is_file():
        raise ValueError(f"Archive ${archive_path} already exists.")

    with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
        readme_path = Path(tmpdir) / "INDEX.txt"
        readme_file = open(readme_path, "w")
        readme_file.write(f"Archive created by Job {job_id} at {datetime.now()}.")
        readme_file.close()

        _add_to_archive(archive_path, archive_password, readme_path)


def _add_to_archive(archive_path: Path, archive_password: str, path_to_add: Path):
    """Add a file or folder to an archive. If the archive does not exist
    it will be created."""
    # TODO catch error like https://stackoverflow.com/a/46098513/166229
    cmd = [
        "7z",
        "a",
        "-p" + archive_password,
        "-mhe=on",
        "-mx1",
        "-y",
        archive_path,
        path_to_add,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL)
    proc.wait()
    (_, stderr) = proc.communicate()
    if proc.returncode != 0:
        raise IOError("Failed to add path to archive (%s)" % stderr)


def _create_destination_name(job):
    dt = job.created.strftime("%Y%m%d")
    username = job.owner.username
    return sanitize_dirname(f"adit_job_{job.id}_{dt}_{username}")
