import logging
import os
import subprocess
import tempfile
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Callable

from celery.contrib.abortable import AbortableTask as AbortableCeleryTask  # pyright: ignore
from dicognito.anonymizer import Anonymizer
from django.conf import settings
from pydicom import Dataset

from ..models import DicomNode, TransferJob, TransferTask
from .dicom_connector import DicomConnector
from .sanitize import sanitize_dirname

logger = logging.getLogger(__name__)


def _create_source_connector(transfer_task: TransferTask) -> DicomConnector:
    # An own function to easily mock the source connector in test_transfer_utils.py
    assert transfer_task.job.source.node_type == DicomNode.NodeType.SERVER
    return DicomConnector(transfer_task.job.source.dicomserver)


def _create_dest_connector(transfer_task: TransferTask) -> DicomConnector:
    # An own function to easily mock the destination connector in test_transfer_utils.py
    assert transfer_task.job.destination.node_type == DicomNode.NodeType.SERVER
    return DicomConnector(transfer_task.job.destination.dicomserver)


class TransferExecutor:
    """
    Executes a transfer task of a selective transfer or batch transfer by utilizing the
    DICOM connector. Transfers only one study or some selected series of one study from
    one patient.
    A long running transfer task can be aborted.
    """

    def __init__(self, transfer_task: TransferTask, celery_task: AbortableCeleryTask) -> None:
        self.transfer_task = transfer_task
        self.celery_task = celery_task

        self.source_connector = _create_source_connector(transfer_task)

        self.dest_connector = None
        if self.transfer_task.job.destination.node_type == DicomNode.NodeType.SERVER:
            self.dest_connector = _create_dest_connector(transfer_task)

    def start(self) -> tuple[TransferTask.Status, str]:
        transfer_job: TransferJob = self.transfer_task.job

        if not transfer_job.source.source_active:
            raise ValueError(f"Source DICOM node not active: {transfer_job.source.name}")

        if not transfer_job.destination.destination_active:
            raise ValueError(f"Destination DICOM node not active: {transfer_job.destination.name}")

        if self.dest_connector:
            self._transfer_to_server()
        else:
            if transfer_job.archive_password:
                self._transfer_to_archive()
            else:
                self._transfer_to_folder()

        return (TransferTask.Status.SUCCESS, "Transfer task completed successfully.")

    def _transfer_to_server(self) -> None:
        with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
            patient_folder = self._download_dicoms(Path(tmpdir))
            assert self.dest_connector
            self.dest_connector.upload_folder(patient_folder)

    def _transfer_to_archive(self) -> None:
        transfer_job: TransferJob = self.transfer_task.job

        assert transfer_job.destination.node_type == DicomNode.NodeType.FOLDER
        archive_folder = Path(transfer_job.destination.dicomfolder.path)
        archive_password = transfer_job.archive_password

        archive_name = f"{self._create_destination_name()}.7z"
        archive_path = archive_folder / archive_name

        if not archive_path.is_file():
            self._create_archive(archive_path, archive_password)

        with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
            patient_folder = self._download_dicoms(Path(tmpdir))
            _add_to_archive(archive_path, archive_password, patient_folder)

    def _transfer_to_folder(self) -> None:
        transfer_job: TransferJob = self.transfer_task.job

        assert transfer_job.destination.node_type == DicomNode.NodeType.FOLDER
        dicom_folder = Path(transfer_job.destination.dicomfolder.path)
        download_folder = dicom_folder / self._create_destination_name()
        self._download_dicoms(download_folder)

    def _download_dicoms(
        self,
        download_folder: Path,
    ) -> Path:
        pseudonym = self.transfer_task.pseudonym
        if pseudonym:
            patient_folder = download_folder / sanitize_dirname(pseudonym)
        else:
            pseudonym = None
            patient_folder = download_folder / sanitize_dirname(self.transfer_task.patient_id)

        # Check if the Study Instance UID is correct and fetch some attributes to create
        # the study folder.
        patient = self._fetch_patient()
        study = self._fetch_study(patient["PatientID"])
        modalities = study["ModalitiesInStudy"]

        modalities = [
            modality for modality in modalities if modality not in settings.EXCLUDED_MODALITIES
        ]

        # If some series are explicitly chosen then check if their Series Instance UIDs
        # are correct and only use those modalities for the name of the study folder.
        series_uids = self.transfer_task.series_uids_list
        if series_uids:
            modalities = set()
            for series_uid in series_uids:
                # TODO: this seems to be very ineffective as we do a c-find for every series
                # in a study and check if it is a wanted series. Better fetch all series of
                # a study and check then.
                for series in self._fetch_series_list(series_uid):
                    modalities.add(series["Modality"])

        study_date = study["StudyDate"]
        study_time = study["StudyTime"]
        modalities = ",".join(modalities)
        prefix = f"{study_date.strftime('%Y%m%d')}-{study_time.strftime('%H%M%S')}"
        study_folder = patient_folder / f"{prefix}-{modalities}"
        os.makedirs(study_folder, exist_ok=True)

        anonymizer = Anonymizer()
        modifier_callback = partial(
            self._modify_dataset,
            anonymizer,
            pseudonym,
        )

        if series_uids:
            self._download_study(
                study,
                study_folder,
                modifier_callback,
                series_uids=series_uids,
            )
        else:
            self._download_study(study, study_folder, modifier_callback)

        return patient_folder

    def _create_destination_name(self) -> str:
        transfer_job = self.transfer_task.job
        name = "adit_"
        name += transfer_job._meta.app_label + "_"
        name += str(transfer_job.id) + "_"
        name += transfer_job.created.strftime("%Y%m%d") + "_"
        name += transfer_job.owner.username
        return sanitize_dirname(name)

    def _fetch_patient(self) -> dict[str, Any]:
        patients = self.source_connector.find_patients({"PatientID": self.transfer_task.patient_id})

        if len(patients) == 0:
            raise ValueError(f"No patient found with Patient ID {self.transfer_task.patient_id}.")

        if len(patients) > 1:
            raise AssertionError(
                f"Multiple patients found with Patient ID {self.transfer_task.patient_id}."
            )

        return patients[0]

    def _fetch_study(self, patient_id: str) -> dict[str, Any]:
        studies = self.source_connector.find_studies(
            {
                "PatientID": patient_id,
                "StudyInstanceUID": self.transfer_task.study_uid,
                "StudyDate": "",
                "StudyTime": "",
                "ModalitiesInStudy": "",
            }
        )

        if len(studies) == 0:
            raise ValueError(
                f"No study found with Study Instance UID {self.transfer_task.study_uid}."
            )
        if len(studies) > 1:
            raise AssertionError(
                f"Multiple studies found with Study Instance UID {self.transfer_task.study_uid}."
            )

        return studies[0]

    def _fetch_series_list(self, series_uid: str) -> list[dict[str, Any]]:
        series_list = self.source_connector.find_series(
            {
                "PatientID": self.transfer_task.patient_id,
                "StudyInstanceUID": self.transfer_task.study_uid,
                "SeriesInstanceUID": "",
                "Modality": "",
            }
        )

        results = []
        for series in series_list:
            if series["SeriesInstanceUID"] == series_uid:
                results.append(series)

        if len(results) == 0:
            raise ValueError(f"No series found with Series Instance UID {series_uid}.")
        if len(results) > 1:
            raise AssertionError(f"Multiple series found with Series Instance UID {series_uid}.")

        return results

    def _download_study(
        self,
        study: dict[str, Any],
        study_folder: Path,
        modifier_callback: Callable,
        series_uids: list[str] = [],
    ) -> None:
        if series_uids:
            for series_uid in series_uids:
                self.source_connector.download_series(
                    study["PatientID"],
                    study["StudyInstanceUID"],
                    series_uid,
                    study_folder,
                    modifier=modifier_callback,
                )
        else:
            self.source_connector.download_study(
                study["PatientID"],
                study["StudyInstanceUID"],
                study_folder,
                modifier=modifier_callback,
            )

    def _modify_dataset(
        self,
        anonymizer: Anonymizer,
        pseudonym: str | None,
        ds: Dataset,
    ) -> None:
        """Optionally pseudonymize an incoming dataset with the given pseudonym
        and add the trial ID and name to the DICOM header if specified."""
        if pseudonym:
            # All dates get pseudonymized, but we want to retain the study date.
            # TODO: Make this configurable.
            study_date = ds.StudyDate

            anonymizer.anonymize(ds)

            ds.StudyDate = study_date

            ds.PatientID = pseudonym
            ds.PatientName = pseudonym

        trial_protocol_id = (self.transfer_task.job.trial_protocol_id,)
        trial_protocol_name = self.transfer_task.job.trial_protocol_name

        if trial_protocol_id:
            ds.ClinicalTrialProtocolID = trial_protocol_id

        if trial_protocol_name:
            ds.ClinicalTrialProtocolName = trial_protocol_name

        if pseudonym and trial_protocol_id:
            session_id = f"{ds.StudyDate}-{ds.StudyTime}"
            ds.PatientComments = (
                f"Project:{trial_protocol_id} Subject:{pseudonym} Session:{pseudonym}_{session_id}"
            )

    def _create_archive(self, archive_path: Path, archive_password: str) -> None:
        """Create a new archive with just an INDEX.txt file in it."""
        if Path(archive_path).is_file():
            raise ValueError(f"Archive ${archive_path} already exists.")

        with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
            readme_path = Path(tmpdir) / "INDEX.txt"
            with open(readme_path, "w", encoding="utf-8") as readme_file:
                readme_file.write(
                    f"Archive created by {self.transfer_task.job} at {datetime.now()}."
                )
            _add_to_archive(archive_path, archive_password, readme_path)


def _add_to_archive(archive_path: Path, archive_password: str, path_to_add: Path) -> None:
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
        raise IOError(f"Failed to add path to archive {stderr}")
