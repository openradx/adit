import io
import logging
from pathlib import Path
from datetime import datetime
import tempfile
import subprocess
from functools import partial
from dicognito.anonymizer import Anonymizer
from django.utils import timezone
from adit.core.models import TransferJob, TransferTask
from ..models import DicomNode
from .dicom_connector import DicomConnector
from .sanitize import sanitize_dirname

logger = logging.getLogger(__name__)


class TransferUtil:  # pylint: disable=too-few-public-methods
    def __init__(self, transfer_task: TransferTask) -> None:
        self.transfer_task = transfer_task
        self.transfer_job: TransferJob = transfer_task.job

        self.source_connector = None
        if self.transfer_job.source.node_type == DicomNode.NodeType.SERVER:
            self.source_connector: DicomConnector = (
                self.transfer_job.source.dicomserver.create_connector()
            )

        self.dest_connector = None
        if self.transfer_job.destination.node_type == DicomNode.NodeType.SERVER:
            self.dest_connector: DicomConnector = (
                self.transfer_job.destination.dicomserver.create_connector()
            )

        self.anonymizer = Anonymizer()

    def start_transfer(self):
        if self.transfer_task.status == TransferTask.Status.CANCELED:
            return self.transfer_task.status

        if self.transfer_task.status != TransferTask.Status.PENDING:
            raise AssertionError(
                f"Invalid status {self.transfer_task.status} of {self.transfer_task}"
            )

        self.transfer_task.status = TransferTask.Status.IN_PROGRESS
        self.transfer_task.start = timezone.now()
        self.transfer_task.save()

        logger.info("Started %s.", self.transfer_job.id)

        handler, stream = self._setup_logger()

        try:
            if not self.transfer_job.source.source_active:
                raise ValueError(
                    f"Source DICOM node not active: {self.transfer_job.source.name}"
                )

            if not self.transfer_job.destination.destination_active:
                raise ValueError(
                    f"Destination DICOM node not active: {self.transfer_job.destination.name}"
                )

            if self.transfer_job.destination.node_type == DicomNode.NodeType.SERVER:
                self._transfer_to_server()
            elif self.transfer_job.destination.node_type == DicomNode.NodeType.FOLDER:
                if self.transfer_job.archive_password:
                    self._transfer_to_archive()
                else:
                    self._transfer_to_folder()
            else:
                raise AssertionError(
                    f"Invalid node type: {self.transfer_job.destination}"
                )

            self.transfer_task.status = TransferTask.Status.SUCCESS
            self.transfer_task.message = "Transfer task completed successfully."

        except Exception as err:  # pylint: disable=broad-except
            logger.exception("Error occurred during %s.", self.transfer_job)
            self.transfer_task.status = TransferTask.Status.FAILURE
            self.transfer_task.message = str(err)
        finally:
            self._save_log_to_task(handler, stream, self.transfer_task)

            self.transfer_task.end = timezone.now()
            self.transfer_task.save()

        return self.transfer_task.status

    # TODO does this really work?
    def _setup_logger(self):
        """Intercept all logger messages to save them later to the task."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.parent.addHandler(handler)

        return handler, stream

    def _save_log_to_task(self, handler, stream, task):
        handler.flush()
        if task.log:
            task.log += "\n" + stream.getvalue()
        else:
            task.log = stream.getvalue()
        stream.close()
        logger.parent.removeHandler(handler)

    def _transfer_to_server(self):
        with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
            patient_folder = self._download_dicoms(Path(tmpdir))
            self.dest_connector.upload_folder(patient_folder)

    def _transfer_to_archive(self):
        archive_folder = Path(self.transfer_job.destination.dicomfolder.path)
        archive_password = self.transfer_job.archive_password

        archive_name = f"{self._create_destination_name()}.7z"
        archive_path = archive_folder / archive_name

        if not archive_path.is_file():
            self._create_archive(archive_path, archive_password)

        with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
            patient_folder = self._download_dicoms(Path(tmpdir))
            self._add_to_archive(archive_path, archive_password, patient_folder)

    def _transfer_to_folder(self):
        dicom_folder = Path(self.transfer_job.destination.dicomfolder.path)
        download_folder = dicom_folder / self._create_destination_name()
        self._download_dicoms(download_folder)

    def _create_destination_name(self):
        dt = self.transfer_job.created.strftime("%Y%m%d")
        username = self.transfer_job.owner.username
        return sanitize_dirname(f"adit_job_{self.transfer_job.id}_{dt}_{username}")

    def _download_dicoms(
        self,
        download_folder: Path,
    ):
        pseudonym = self.transfer_task.pseudonym
        if pseudonym:
            patient_folder = download_folder / sanitize_dirname(pseudonym)
        else:
            pseudonym = None
            patient_folder = download_folder / sanitize_dirname(
                self.transfer_task.patient_id
            )

        # Check if the Study Instance UID is correct and fetch some attributes to create
        # the study folder.
        study = self._fetch_study()
        modalities = study["ModalitiesInStudy"]

        # If some series are explicitly chosen then check if their Series Instance UIDs
        # are correct and only use their modalities for the name of the study folder.
        if self.transfer_task.series_uids:
            modalities = set()
            for series in self._fetch_series_list():
                modalities.add(series["Modality"])

        study_date = study["StudyDate"]
        study_time = study["StudyTime"]
        modalities = ",".join(modalities)
        prefix = f"{study_date.strftime('%Y%m%d')}-{study_time.strftime('%H%M%S')}"
        study_folder = patient_folder / f"{prefix}-{modalities}"
        study_folder.mkdir(parents=True, exist_ok=True)

        modifier_callback = partial(
            self._modify_dataset,
            pseudonym,
            self.transfer_job.trial_protocol_id,
            self.transfer_job.trial_protocol_name,
        )

        if self.transfer_task.series_uids:
            # Download only the specified series of a study.
            self._download_series(
                study,
                self.transfer_task.series_uids,
                study_folder,
                modifier_callback,
            )
        else:
            # Download the whole study.
            self._download_study(study, study_folder, modifier_callback)

        return patient_folder

    def _fetch_study(self):
        studies = self.source_connector.find_studies(
            {
                "PatientID": self.transfer_task.patient_id,
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

    def _fetch_series_list(self):
        series_list = self.source_connector.find_series(
            {
                "PatientID": self.transfer_task.patient_id,
                "StudyInstanceUID": self.transfer_task.study_uid,
                "SeriesInstanceUID": "",
                "Modality": "",
            }
        )

        results = []
        for series_uid in self.transfer_task.series_uids:
            found = []
            for series in series_list:
                if series["SeriesInstanceUID"] == series_uid:
                    found.append(series)

            if len(found) == 0:
                raise ValueError(
                    f"No series found with Series Instance UID {series_uid}."
                )
            if len(found) > 1:
                raise AssertionError(
                    f"Multiple series found with Series Instance UID {series_uid}."
                )

            results.append(found[0])

        return results

    def _download_study(self, study, study_folder, modifier_callback):
        self.source_connector.download_study(
            study["PatientID"],
            study["StudyInstanceUID"],
            study_folder,
            modifier_callback=modifier_callback,
        )

    def _download_series(
        self,
        study,
        series_uids,
        study_folder,
        modifier_callback,
    ):
        for series_uid in series_uids:
            series_list = self.source_connector.find_series(
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

            self.source_connector.download_series(
                series["PatientID"],
                series["StudyInstanceUID"],
                series["SeriesInstanceUID"],
                series_folder,
                modifier_callback,
            )

    def _modify_dataset(self, pseudonym, trial_protocol_id, trial_protocol_name, ds):
        """Optionally pseudonymize an incoming dataset with the given pseudonym
        and add the trial ID and name to the DICOM header if specified."""
        if pseudonym:
            self.anonymizer.anonymize(ds)
            ds.PatientID = pseudonym
            ds.PatientName = pseudonym

        if trial_protocol_id:
            ds.ClinicalTrialProtocolID = trial_protocol_id

        if trial_protocol_name:
            ds.ClinicalTrialProtocolName = trial_protocol_name

    def _create_archive(self, archive_path: Path, archive_password: str):
        """Create a new archive with just an INDEX.txt file in it."""
        if Path(archive_path).is_file():
            raise ValueError(f"Archive ${archive_path} already exists.")

        with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
            readme_path = Path(tmpdir) / "INDEX.txt"
            readme_file = open(readme_path, "w")
            readme_file.write(
                f"Archive created by Job {self.transfer_job.id} at {datetime.now()}."
            )
            readme_file.close()

            self._add_to_archive(archive_path, archive_password, readme_path)

    def _add_to_archive(
        self, archive_path: Path, archive_password: str, path_to_add: Path
    ):
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
