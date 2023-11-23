import logging
import os
import subprocess
import tempfile
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Callable

from dicognito.anonymizer import Anonymizer
from dicognito.value_keeper import ValueKeeper
from django.conf import settings
from pydicom import Dataset

from ..errors import DicomError
from ..models import DicomNode, TransferTask
from ..types import DicomLogEntry
from .dicom_dataset import QueryDataset, ResultDataset
from .dicom_operator import DicomOperator
from .sanitize import sanitize_dirname

logger = logging.getLogger(__name__)


class TransferExecutor:
    """
    Executes a transfer task of a selective transfer or batch transfer by utilizing the
    DICOM operator. Transfers only a single study or some selected series of a single study.
    """

    def __init__(self, transfer_task: TransferTask) -> None:
        self.transfer_task = transfer_task

        source = self.transfer_task.source
        assert source.node_type == DicomNode.NodeType.SERVER
        self.source_operator = DicomOperator(source.dicomserver)

        self.dest_operator = None
        destination = self.transfer_task.destination
        if destination.node_type == DicomNode.NodeType.SERVER:
            self.dest_operator = DicomOperator(destination.dicomserver)

    def start(self) -> tuple[TransferTask.Status, str, list[DicomLogEntry]]:
        if self.dest_operator:
            self._transfer_to_server()
        else:
            if self.transfer_task.job.archive_password:
                self._transfer_to_archive()
            else:
                self._transfer_to_folder()

        logs: list[DicomLogEntry] = []
        for log in self.source_operator.get_logs():
            logs.append(log)
        self.source_operator.clear_logs()

        if self.dest_operator:
            for log in self.dest_operator.get_logs():
                logs.append(log)
            self.dest_operator.clear_logs()

        status: TransferTask.Status = TransferTask.Status.SUCCESS
        message: str = "Transfer task completed successfully."
        for log in logs:
            if log["level"] == "Warning":
                status = TransferTask.Status.WARNING
                message = "Transfer task finished with warnings."

        return (status, message, logs)

    def _transfer_to_server(self) -> None:
        with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
            patient_folder = self._download_dicoms(Path(tmpdir))
            assert self.dest_operator
            self.dest_operator.upload_instances(patient_folder)

    def _transfer_to_archive(self) -> None:
        assert self.transfer_task.destination.node_type == DicomNode.NodeType.FOLDER
        archive_folder = Path(self.transfer_task.destination.dicomfolder.path)
        archive_password = self.transfer_task.job.archive_password

        archive_name = f"{self._create_destination_name()}.7z"
        archive_path = archive_folder / archive_name

        if not archive_path.is_file():
            self._create_archive(archive_path, archive_password)

        with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
            patient_folder = self._download_dicoms(Path(tmpdir))
            _add_to_archive(archive_path, archive_password, patient_folder)

    def _transfer_to_folder(self) -> None:
        assert self.transfer_task.destination.node_type == DicomNode.NodeType.FOLDER
        dicom_folder = Path(self.transfer_task.destination.dicomfolder.path)
        download_folder = dicom_folder / self._create_destination_name()
        self._download_dicoms(download_folder)

    def _create_destination_name(self) -> str:
        transfer_job = self.transfer_task.job
        name = "adit_"
        name += transfer_job._meta.app_label + "_"
        name += str(transfer_job.id) + "_"
        name += transfer_job.created.strftime("%Y%m%d") + "_"
        name += transfer_job.owner.username
        return sanitize_dirname(name)

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
        study = self._fetch_study(patient_id=patient.PatientID)
        modalities = study.ModalitiesInStudy

        modalities = [
            modality for modality in modalities if modality not in settings.EXCLUDED_MODALITIES
        ]

        # If some series are explicitly chosen then check if their Series Instance UIDs
        # are correct and only use those modalities for the name of the study folder.
        series_uids = self.transfer_task.series_uids
        if series_uids:
            modalities = set()
            for series_uid in series_uids:
                # TODO: this seems to be very ineffective as we do a c-find for every series
                # in a study and check if it is a wanted series. Better fetch all series of
                # a study and check then.
                for series in self._fetch_series_list(series_uid=series_uid):
                    modalities.add(series.Modality)

        study_date = study.StudyDate
        study_time = study.StudyTime
        modalities = ",".join(modalities)
        prefix = f"{study_date.strftime('%Y%m%d')}-{study_time.strftime('%H%M%S')}"
        study_folder = patient_folder / f"{prefix}-{modalities}"
        os.makedirs(study_folder, exist_ok=True)

        anonymizer = self._setup_anonymizer()

        modifier = partial(
            self._modify_dataset,
            anonymizer,
            pseudonym,
        )

        if series_uids:
            self._download_study(
                study.PatientID,
                study.StudyInstanceUID,
                study_folder,
                modifier,
                series_uids=series_uids,
            )
        else:
            self._download_study(
                study.PatientID,
                study.StudyInstanceUID,
                study_folder,
                modifier,
            )

        return patient_folder

    def _fetch_patient(self) -> ResultDataset:
        patients = list(
            self.source_operator.find_patients(
                QueryDataset.create(PatientID=self.transfer_task.patient_id)
            )
        )

        if len(patients) == 0:
            raise DicomError(f"No patient found with Patient ID {self.transfer_task.patient_id}.")

        if len(patients) > 1:
            raise DicomError(
                f"Multiple patients found with Patient ID {self.transfer_task.patient_id}."
            )

        return patients[0]

    def _fetch_study(self, patient_id: str) -> ResultDataset:
        studies = list(
            self.source_operator.find_studies(
                QueryDataset.create(
                    PatientID=patient_id,
                    StudyInstanceUID=self.transfer_task.study_uid,
                )
            )
        )

        if len(studies) == 0:
            raise DicomError(
                f"No study found with Study Instance UID {self.transfer_task.study_uid}."
            )
        if len(studies) > 1:
            raise DicomError(
                f"Multiple studies found with Study Instance UID {self.transfer_task.study_uid}."
            )

        return studies[0]

    def _fetch_series_list(self, series_uid: str) -> list[ResultDataset]:
        series_list = list(
            self.source_operator.find_series(
                QueryDataset.create(
                    PatientID=self.transfer_task.patient_id,
                    StudyInstanceUID=self.transfer_task.study_uid,
                )
            )
        )

        results = []
        for series in series_list:
            if series.SeriesInstanceUID == series_uid:
                results.append(series)

        if len(results) == 0:
            raise DicomError(f"No series found with Series Instance UID {series_uid}.")
        if len(results) > 1:
            raise DicomError(f"Multiple series found with Series Instance UID {series_uid}.")

        return results

    def _setup_anonymizer(self) -> Anonymizer:
        anonymizer = Anonymizer()
        for element in settings.SKIP_ELEMENTS_ANONYMIZATION:
            anonymizer.add_element_handler(ValueKeeper(element))
        return anonymizer

    def _download_study(
        self,
        patient_id: str,
        study_uid: str,
        study_folder: Path,
        modifier: Callable,
        series_uids: list[str] = [],
    ) -> None:
        if series_uids:
            for series_uid in series_uids:
                self.source_operator.download_series(
                    patient_id=patient_id,
                    study_uid=study_uid,
                    series_uid=series_uid,
                    dest_folder=study_folder,
                    modifier=modifier,
                )
        else:
            self.source_operator.download_study(
                patient_id=patient_id,
                study_uid=study_uid,
                dest_folder=study_folder,
                modifier=modifier,
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
            anonymizer.anonymize(ds)

            ds.PatientID = pseudonym
            ds.PatientName = pseudonym

        trial_protocol_id = self.transfer_task.job.trial_protocol_id
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
            raise DicomError(f"Archive ${archive_path} already exists.")

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
        raise DicomError(f"Failed to add path to archive: {stderr}")
