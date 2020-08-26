import logging
from pathlib import Path
from datetime import datetime
import shutil
import tempfile
import subprocess
from functools import partial
from celery import shared_task
from django.conf import settings
from .utils.dicom_connector import DicomConnector
from .utils.anonymizer import Anonymizer
from .models import DicomNode, TransferTask

logger = logging.getLogger("adit." + __name__)


@shared_task
def transfer_dicoms(task_id):
    task = TransferTask.objects.get(id=task_id)

    if task.status != TransferTask.Status.PENDING:
        raise AssertionError(f"Invalid transfer task status: {task.status}")

    task.status = TransferTask.Status.IN_PROGRESS
    task.save()

    job = task.job

    try:
        if job.destination.node_type == DicomNode.NodeType.SERVER:
            _transfer_to_server(task)
        else:
            assert job.destination.node_type == DicomNode.NodeType.FOLDER
            if job.archive_password:
                _transfer_to_archive(task)
            else:
                _transfer_to_folder(task)

        task.status = TransferTask.Status.SUCCESS
        task.save()

    except Exception as err:  # pylint: disable=broad-except
        task.status = TransferTask.Status.FAILURE
        task.message = str(err)
        task.save()

    return task.status


def _transfer_to_server(transfer_task: TransferTask):
    job = transfer_task.job
    source_connector = job.source.create_connector()
    dest_connector = job.destination.create_connector()
    temp_folder = tempfile.mkdtemp(dir=settings.ADIT_CACHE_FOLDER)

    study_folder = _download_dicoms(source_connector, transfer_task, temp_folder)
    dest_connector.upload_folder(study_folder)
    shutil.rmtree(study_folder)


def _transfer_to_archive(transfer_task: TransferTask):
    job = transfer_task.job
    source_connector = job.source.create_connector()
    username = job.created_by.username
    archive_folder = Path(job.destination)
    archive_password = job.archive_password
    archive_path = _create_archive(username, archive_folder, archive_password)
    temp_folder = tempfile.mkdtemp(dir=settings.ADIT_CACHE_FOLDER)

    study_folder = _download_dicoms(source_connector, transfer_task, temp_folder)
    _add_to_archive(archive_path, archive_password, study_folder)
    shutil.rmtree(study_folder)


def _transfer_to_folder(transfer_task: TransferTask):
    job = transfer_task.job
    source_connector = job.source.create_connector()
    dest_folder = Path(job.destination)

    _download_dicoms(source_connector, transfer_task, dest_folder)


def _download_dicoms(
    connector: DicomConnector, transfer_task: TransferTask, folder: Path
):
    pseudonym = transfer_task.pseudonym
    patient_id = transfer_task.patient_id
    if pseudonym:
        patient_folder = folder / pseudonym
    else:
        pseudonym = None
        patient_folder = folder / patient_id

    studies = connector.find_studies(
        patient_id=patient_id, study_uid=transfer_task.study_uid
    )
    if len(studies) == 0:
        raise AssertionError(
            f"No study found with Study Instance UID: {transfer_task.study_uid}"
        )
    if len(studies) > 1:
        raise AssertionError(
            f"Multiple studies found with Study Instance UID {transfer_task.study_uid}."
        )

    study = studies[0]
    study_date = study["StudyDate"]
    study_time = study["StudyTime"]
    modalities = ",".join(study["Modalities"])
    study_folder = patient_folder / f"{study_date}-{study_time}-{modalities}"
    study_folder.mkdir(parents=True, exist_ok=True)

    job = transfer_task.job
    modifier_callback = partial(
        _modify_dataset, job.trial_protocol_id, job.trial_protocol_name, pseudonym
    )

    if transfer_task.series_uids:
        # Download specific series of a study only.
        _download_series(
            connector, study, transfer_task.series_uids, study_folder, modifier_callback
        )
    else:
        # Download the whole study.
        _download_study(connector, study, study_folder, modifier_callback)

    return study_folder


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
            study["PatientID"], study["StudyInstanceUID"], series_uid
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
        series_folder_name = series["SeriesDescription"]
        series_folder = study_folder / series_folder_name

        connector.download_series(
            series["PatientID"],
            series["StudyInstanceUID"],
            series["SeriesInstanceUID"],
            series_folder,
            modifier_callback,
        )


def _modify_dataset(pseudonym, trial_protocol_id, trial_protocol_name, ds):
    """Optionally pseudonymize an incoming dataset with the given pseudonym
        and add the trial ID and name to the DICOM header if specified."""
    if pseudonym:
        anonymizer = Anonymizer()
        anonymizer.anonymize_dataset(ds, patient_name=pseudonym)

    if trial_protocol_id:
        ds.ClinicalTrialProtocolID = trial_protocol_id

    if trial_protocol_name:
        ds.ClinicalTrialProtocolName = trial_protocol_name


def _create_archive(username: str, archive_folder: Path, archive_password: str):
    """Create a new archive with just an INDEX.txt file in it."""
    temp_folder = tempfile.mkdtemp(dir=settings.ADIT_CACHE_FOLDER)
    readme_path = Path(temp_folder) / "INDEX.txt"
    readme_file = open(readme_path, "w")
    readme_file.write(f"Archive created by {username} at {datetime.now()}.")
    readme_file.close()

    archive_name = f"{username}_{datetime.now().isoformat()}.7z"
    archive_path = archive_folder / archive_name
    if Path(archive_path).is_file():
        raise ValueError(f"Archive ${archive_path} already exists.")

    _add_to_archive(archive_path, archive_password, readme_path)
    shutil.rmtree(temp_folder)
    return archive_path


def _add_to_archive(archive_path, archive_password, path_to_add):
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
