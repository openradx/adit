import io
import logging
from pathlib import Path
from datetime import datetime
import tempfile
import subprocess
from functools import partial
from typing import Any, Callable, Dict, List, Tuple
from dicognito.anonymizer import Anonymizer
from pydicom import Dataset
from django.utils import timezone
from adit.core.models import TransferJob, TransferTask
from ..models import DicomNode
from .dicom_connector import DicomConnector
from .sanitize import sanitize_dirname

logger = logging.getLogger(__name__)


def execute_transfer(transfer_task: TransferTask) -> TransferTask.Status:
    if transfer_task.status == TransferTask.Status.CANCELED:
        return transfer_task.status

    if transfer_task.status != TransferTask.Status.PENDING:
        raise AssertionError(
            f"Invalid status {transfer_task.status} of {transfer_task}"
        )

    transfer_task.status = TransferTask.Status.IN_PROGRESS
    transfer_task.start = timezone.now()
    transfer_task.save()

    logger.info("Started %s.", transfer_task)

    handler, stream = _setup_logger()

    transfer_job: TransferJob = transfer_task.job

    try:
        if not transfer_job.source.source_active:
            raise ValueError(
                f"Source DICOM node not active: {transfer_job.source.name}"
            )

        if not transfer_job.destination.destination_active:
            raise ValueError(
                f"Destination DICOM node not active: {transfer_job.destination.name}"
            )

        if transfer_job.destination.node_type == DicomNode.NodeType.SERVER:
            _transfer_to_server(transfer_task)
        elif transfer_job.destination.node_type == DicomNode.NodeType.FOLDER:
            if transfer_job.archive_password:
                _transfer_to_archive(transfer_task)
            else:
                _transfer_to_folder(transfer_task)
        else:
            raise AssertionError(f"Invalid node type: {transfer_job.destination}")

        transfer_task.status = TransferTask.Status.SUCCESS
        transfer_task.message = "Transfer task completed successfully."

    except Exception as err:  # pylint: disable=broad-except
        logger.exception("Error occurred during %s.", transfer_job)
        transfer_task.status = TransferTask.Status.FAILURE
        transfer_task.message = str(err)
    finally:
        _save_log_to_task(handler, stream, transfer_task)

        transfer_task.end = timezone.now()
        transfer_task.save()

    return transfer_task.status


# TODO does this really work?
def _setup_logger() -> Tuple[logging.StreamHandler, io.StringIO]:
    """Intercept all logger messages to save them later to the task."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.parent.addHandler(handler)

    return handler, stream


def _save_log_to_task(
    handler: logging.StreamHandler, stream: io.StringIO, transfer_task: TransferTask
) -> None:
    handler.flush()
    if transfer_task.log:
        transfer_task.log += "\n" + stream.getvalue()
    else:
        transfer_task.log = stream.getvalue()
    stream.close()
    logger.parent.removeHandler(handler)


def _transfer_to_server(transfer_task: TransferTask) -> None:
    with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
        patient_folder = _download_dicoms(transfer_task, Path(tmpdir))
        connector = _create_dest_connector(transfer_task)
        connector.upload_folder(patient_folder)


def _create_dest_connector(transfer_task: TransferTask) -> DicomConnector:
    # An own method to easily mock the destination connector in the test
    return transfer_task.job.destination.dicomserver.create_connector()


def _transfer_to_archive(transfer_task: TransferTask) -> None:
    transfer_job: TransferJob = transfer_task.job

    archive_folder = Path(transfer_job.destination.dicomfolder.path)
    archive_password = transfer_job.archive_password

    archive_name = f"{_create_destination_name(transfer_job)}.7z"
    archive_path = archive_folder / archive_name

    if not archive_path.is_file():
        _create_archive(archive_path, transfer_job.id, archive_password)

    with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
        patient_folder = _download_dicoms(transfer_task, Path(tmpdir))
        _add_to_archive(archive_path, archive_password, patient_folder)


def _transfer_to_folder(transfer_task: TransferTask) -> None:
    transfer_job: TransferJob = transfer_task.job
    dicom_folder = Path(transfer_job.destination.dicomfolder.path)
    download_folder = dicom_folder / _create_destination_name(transfer_job)
    _download_dicoms(transfer_task, download_folder)


def _create_destination_name(transfer_job) -> str:
    dt = transfer_job.created.strftime("%Y%m%d")
    username = transfer_job.owner.username
    return sanitize_dirname(f"adit_job_{transfer_job.id}_{dt}_{username}")


def _download_dicoms(
    transfer_task: TransferTask,
    download_folder: Path,
) -> Path:
    pseudonym = transfer_task.pseudonym
    if pseudonym:
        patient_folder = download_folder / sanitize_dirname(pseudonym)
    else:
        pseudonym = None
        patient_folder = download_folder / sanitize_dirname(transfer_task.patient_id)

    connector = _create_source_connector(transfer_task)

    # Check if the Study Instance UID is correct and fetch some attributes to create
    # the study folder.
    study = _fetch_study(connector, transfer_task)
    modalities = study["ModalitiesInStudy"]

    # If some series are explicitly chosen then check if their Series Instance UIDs
    # are correct and only use their modalities for the name of the study folder.
    if transfer_task.series_uids:
        modalities = set()
        for series in _fetch_series_list(connector, transfer_task):
            modalities.add(series["Modality"])

    study_date = study["StudyDate"]
    study_time = study["StudyTime"]
    modalities = ",".join(modalities)
    prefix = f"{study_date.strftime('%Y%m%d')}-{study_time.strftime('%H%M%S')}"
    study_folder = patient_folder / f"{prefix}-{modalities}"
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
        # Download only the specified series of a study.
        _download_series(
            connector,
            study,
            transfer_task.series_uids,
            study_folder,
            modifier_callback,
        )
    else:
        # Download the whole study.
        _download_study(connector, study, study_folder, modifier_callback)

    return patient_folder


def _create_source_connector(transfer_task: TransferTask) -> DicomConnector:
    # An own method to easily mock the source connector in the test
    return transfer_task.job.source.dicomserver.create_connector()


def _fetch_study(
    connector: DicomConnector, transfer_task: TransferTask
) -> Dict[str, Any]:
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
        raise ValueError(
            f"No study found with Study Instance UID {transfer_task.study_uid}."
        )
    if len(studies) > 1:
        raise AssertionError(
            f"Multiple studies found with Study Instance UID {transfer_task.study_uid}."
        )

    return studies[0]


def _fetch_series_list(
    connector: DicomConnector, transfer_task: TransferTask
) -> List[Dict[str, Any]]:
    series_list = connector.find_series(
        {
            "PatientID": transfer_task.patient_id,
            "StudyInstanceUID": transfer_task.study_uid,
            "SeriesInstanceUID": "",
            "Modality": "",
        }
    )

    results = []
    for series_uid in transfer_task.series_uids:
        found = []
        for series in series_list:
            if series["SeriesInstanceUID"] == series_uid:
                found.append(series)

        if len(found) == 0:
            raise ValueError(f"No series found with Series Instance UID {series_uid}.")
        if len(found) > 1:
            raise AssertionError(
                f"Multiple series found with Series Instance UID {series_uid}."
            )

        results.append(found[0])

    return results


def _download_study(
    connector: DicomConnector,
    study: Dict[str, Any],
    study_folder: Path,
    modifier_callback: Callable,
) -> None:
    connector.download_study(
        study["PatientID"],
        study["StudyInstanceUID"],
        study_folder,
        modifier_callback=modifier_callback,
    )


def _download_series(
    connector: DicomConnector,
    study: Dict[str, Any],
    series_uids: List[str],
    study_folder: Path,
    modifier_callback: Callable,
) -> None:
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


def _modify_dataset(
    anonymizer: Anonymizer,
    pseudonym: str,
    trial_protocol_id: str,
    trial_protocol_name: str,
    ds: Dataset,
) -> None:
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


def _create_archive(archive_path: Path, job_id: int, archive_password: str) -> None:
    """Create a new archive with just an INDEX.txt file in it."""
    if Path(archive_path).is_file():
        raise ValueError(f"Archive ${archive_path} already exists.")

    with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
        readme_path = Path(tmpdir) / "INDEX.txt"
        readme_file = open(readme_path, "w")
        readme_file.write(f"Archive created by Job {job_id} at {datetime.now()}.")
        readme_file.close()

        _add_to_archive(archive_path, archive_password, readme_path)


def _add_to_archive(
    archive_path: Path, archive_password: str, path_to_add: Path
) -> None:
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
