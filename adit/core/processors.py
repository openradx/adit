import abc
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

from .errors import DicomError
from .models import DicomAppSettings, DicomNode, DicomTask, TransferTask
from .types import DicomLogEntry, ProcessingResult
from .utils.dicom_dataset import QueryDataset, ResultDataset
from .utils.dicom_operator import DicomOperator
from .utils.dicom_utils import write_dataset
from .utils.sanitize import sanitize_dirname

logger = logging.getLogger(__name__)


class DicomTaskProcessor(abc.ABC):
    app_name: str
    dicom_task_class: type[DicomTask]
    app_settings_class: type[DicomAppSettings]

    def __init__(self, dicom_task: DicomTask) -> None:
        self.dicom_task = dicom_task

    def is_suspended(self) -> bool:
        app_settings = self.app_settings_class.get()
        assert isinstance(app_settings, DicomAppSettings)
        return app_settings.suspended

    @abc.abstractmethod
    def process(self) -> ProcessingResult:
        """Does the actual work of processing the dicom task.

        Should return a tuple of the final status of that task, a message that is
        stored in the task model and a list of log entries (e.g. warnings).
        """
        ...


class TransferTaskProcessor(DicomTaskProcessor):
    _logs: list[DicomLogEntry] = []

    def __init__(self, dicom_task: DicomTask) -> None:
        assert isinstance(dicom_task, TransferTask)
        self.transfer_task = dicom_task

        source = self.transfer_task.source
        assert source.node_type == DicomNode.NodeType.SERVER
        self.source_operator = DicomOperator(source.dicomserver)

        self.dest_operator = None
        destination = self.transfer_task.destination
        if destination.node_type == DicomNode.NodeType.SERVER:
            self.dest_operator = DicomOperator(destination.dicomserver)

    def get_logs(self) -> list[DicomLogEntry]:
        logs: list[DicomLogEntry] = []
        logs.extend(self.source_operator.get_logs())
        if self.dest_operator:
            logs.extend(self.dest_operator.get_logs())
        logs.extend(self._logs)
        return logs

    def process(self) -> ProcessingResult:
        if self.dest_operator:
            self._transfer_to_server()
        else:
            if self.transfer_task.job.archive_password:
                self._transfer_to_archive()
            else:
                self._transfer_to_folder()

        status: TransferTask.Status = TransferTask.Status.SUCCESS
        message: str = "Transfer task completed successfully."
        logs = self.get_logs()
        for log in logs:
            if log["level"] == "Warning":
                status = TransferTask.Status.WARNING
                message = log["title"]

        return {
            "status": status,
            "message": message,
            "log": "\n".join([log["message"] for log in logs]),
        }

    def _transfer_to_server(self) -> None:
        with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
            patient_folder = self._download_dicoms(Path(tmpdir))
            assert self.dest_operator
            self.dest_operator.upload_instances(patient_folder)

    def _transfer_to_archive(self) -> None:
        assert self.transfer_task.destination.node_type == DicomNode.NodeType.FOLDER
        archive_folder = Path(self.transfer_task.destination.dicomfolder.path)
        archive_password = self.transfer_task.job.archive_password

        if settings.SELECTIVE_TRANSFER_ARCHIVE_TYPE == "7z":
            suffix = ".7z"
        elif settings.SELECTIVE_TRANSFER_ARCHIVE_TYPE == "zip":
            suffix = ".zip"
        else:
            raise DicomError(
                f"Unsupported archive type: {settings.SELECTIVE_TRANSFER_ARCHIVE_TYPE}"
            )

        archive_name = f"{self._create_destination_name()}{suffix}"
        archive_path = archive_folder / archive_name

        if not archive_path.is_file():
            logger.debug(f"Creating archive at {archive_path}")

            with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
                readme_path = Path(tmpdir) / "INDEX.txt"
                with open(readme_path, "w", encoding="utf-8") as readme_file:
                    readme_file.write(
                        f"Archive created by {self.transfer_task.job} at {datetime.now()}."
                    )
                _add_to_archive(archive_path, archive_password, readme_path)

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

        study = self._find_study()
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
                for series in self._find_series_list(series_uid=series_uid):
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

    def _find_study(self) -> ResultDataset:
        studies = list(
            self.source_operator.find_studies(
                QueryDataset.create(
                    PatientID=self.transfer_task.patient_id,
                    StudyInstanceUID=self.transfer_task.study_uid,
                )
            )
        )

        if len(studies) == 0:
            # It could be that the PatientID of the patient changed, because the patient was
            # reassigned to another patient (e.g. if it is an external investigation).
            # So we try to find the study with the StudyInstanceUID only and later warn
            # that there PatientIDs differ (see below).
            studies = list(
                self.source_operator.find_studies(
                    QueryDataset.create(StudyInstanceUID=self.transfer_task.study_uid)
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

        study = studies[0]
        task_patient_id = self.transfer_task.patient_id
        study_patient_id = study.PatientID
        if task_patient_id != study_patient_id:
            self._logs.append(
                {
                    "level": "Warning",
                    "title": "Mismatching PatientIDs",
                    "message": (
                        "Mismatching PatientID in the transfer task "
                        f"({task_patient_id}) and the found study ({study_patient_id})."
                    ),
                }
            )

        return study

    def _find_series_list(self, series_uid: str) -> list[ResultDataset]:
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
        series_uids: list[str] | None = None,
    ) -> None:
        def callback(ds: Dataset | None) -> None:
            if ds is None:
                return

            modifier(ds)

            folder_path = Path(study_folder)
            file_name = f"{ds.SOPInstanceUID}.dcm"
            file_path = folder_path / file_name
            folder_path.mkdir(parents=True, exist_ok=True)
            write_dataset(ds, file_path)

        if series_uids:
            for series_uid in series_uids:
                self.source_operator.fetch_series(
                    patient_id=patient_id,
                    study_uid=study_uid,
                    series_uid=series_uid,
                    callback=callback,
                )
        else:
            # If no series are explicitly chosen then download all series of the study
            self.source_operator.fetch_study(
                patient_id=patient_id,
                study_uid=study_uid,
                callback=callback,
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


def _add_to_archive(archive_path: Path, archive_password: str, path_to_add: Path) -> None:
    """Add a file or folder to an archive. If the archive does not exist
    it will be created."""
    cmd = ["7z", "a", "-y", "-mx1", f"-p{archive_password}"]

    if settings.SELECTIVE_TRANSFER_ARCHIVE_TYPE == "7z":
        cmd.extend(["-t7z", "-mhe=on"])
    elif settings.SELECTIVE_TRANSFER_ARCHIVE_TYPE == "zip":
        cmd.extend(["-tzip"])
    else:
        raise DicomError(f"Unsupported archive type: {settings.SELECTIVE_TRANSFER_ARCHIVE_TYPE}")

    cmd.extend([str(archive_path), str(path_to_add)])

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL)
    proc.wait()
    (_, stderr) = proc.communicate()
    if proc.returncode != 0:
        raise DicomError(f"Failed to add path {path_to_add} to archive {archive_path}: {stderr}")
