import logging
import shutil
import tempfile
import subprocess
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Union
from time import sleep
from main.utils.dicom_connector import DicomConnector
from main.utils.anonymizer import Anonymizer

logger = logging.getLogger("adit." + __name__)


class BatchTransferHandler:

    SUCCESS = "Success"
    FAILURE = "Failure"

    @dataclass
    class Config:
        username: str
        trial_protocol_id: str = None
        trial_protocol_name: str = None
        archive_password: str = None
        cache_folder: str = "/tmp"
        batch_timeout: int = 3

    def __init__(
        self,
        config: Config,
        source: DicomConnector,
        destination: Union[DicomConnector, Path],
    ):
        self.config = config
        self.source = source
        self.destination = destination
        self._anonymizer = Anonymizer()
        self.patient_cache = dict()

    def _create_archive(self, archive_name):
        """Create a new archive with just an INDEX.txt file in it."""
        temp_folder = tempfile.mkdtemp(dir=self.config.cache_folder)

        readme_path = Path(temp_folder) / "INDEX.txt"
        readme_file = open(readme_path, "w")
        readme_file.write(
            f"Archive created by {self.config.username} at {datetime.now()}."
        )
        readme_file.close()

        archive_path = self.destination / archive_name
        if Path(archive_path).is_file():
            raise ValueError(f"Archive ${archive_path} already exists.")

        self._add_to_archive(readme_path, archive_name)

        shutil.rmtree(temp_folder)

    def _add_to_archive(self, path_to_add, archive_name):
        """Add a file or folder to an archive. If the archive does not exist
        it will be created."""
        # TODO catch error like https://stackoverflow.com/a/46098513/166229
        archive_path = self.destination / f"{archive_name}.7z"
        cmd = [
            "7z",
            "a",
            "-p" + self.config.archive_password,
            "-mhe=on",
            "-mx1",
            "-y",
            archive_path,
            path_to_add,
        ]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL)
            proc.wait()
            (_, stderr) = proc.communicate()
            if proc.returncode != 0:
                raise Exception("Failed to add path to archive (%s)" % stderr)
        except Exception as err:
            raise Exception("Failure while executing 7zip: %s" % str(err))

    def _fetch_patient(self, request):
        """Fetch the correct patient for this request. Raises an error if there
        are multiple patients for this request."""

        request_id = request["RequestID"]

        patient_id = request["PatientID"]
        patient_name = request["PatientName"]
        patient_birth_date = request["PatientBirthDate"]

        patient_key = f"{patient_id}__{patient_name}__{patient_birth_date}"
        if patient_key in self.patient_cache:
            return self.patient_cache[patient_key]

        patients = self.source.find_patients(
            patient_id, patient_name, patient_birth_date
        )
        if len(patients) != 1:
            raise Exception(f"Ambigious patient for request with ID {request_id}.")

        patient = patients[0]
        patient_id = patient["PatientID"]
        patient_name = patient["PatientName"]
        patient_birth_date = patient["PatientBirthDate"]

        patient_key = f"{patient_id}__{patient_name}__{patient_birth_date}"
        self.patient_cache[patient_key] = patient

        return patient

    def _modify_dataset(self, pseudonym, ds):
        """Optionally pseudonymize an incoming dataset with the given pseudonym
        and add the trial ID and name to the DICOM header if specified."""

        if pseudonym:
            self._anonymizer.anonymize_dataset(ds, patient_name=pseudonym)

        if self.config.trial_protocol_id:
            ds.ClinicalTrialProtocolID = self.config.trial_protocol_id

        if self.config.trial_protocol_name:
            ds.ClinicalTrialProtocolName = self.config.trial_protocol_name

    def _download_request(self, request, folder_path):
        patient_id = self._fetch_patient(request)["PatientID"]

        pseudonym = request["Pseudonym"]
        if pseudonym:
            patient_folder = Path(folder_path) / pseudonym
        else:
            pseudonym = None
            patient_folder = Path(folder_path) / patient_id

        patient_folder.mkdir(exist_ok=True)

        if request["AccessionNumber"]:
            study_list = self.source.find_studies(
                accession_number=request["AccessionNumber"]
            )
        else:
            study_list = self.source.find_studies(
                patient_id=patient_id,
                study_date=request["StudyDate"],
                modality=request["Modality"],
            )

        for study in study_list:
            study_date = study["StudyDate"]
            study_time = study["StudyTime"]
            modalities = ",".join(study["Modalities"])
            study_folder = patient_folder / f"{study_date}-{study_time}-{modalities}"
            modifier_callback = partial(self._modify_dataset, pseudonym)
            self.source.download_study(
                patient_id,
                study["StudyInstanceUID"],
                study_folder,
                modifier_callback=modifier_callback,
            )

        return patient_folder, pseudonym

    def _process_requests(self, requests, folder_path, process_callback):
        """The heart of the batch transferrer which handles each request, download the
        DICOM data, calls a handler to process it and optionally cleans everything up."""

        for i, request in enumerate(requests):
            request_id = request["RequestID"]

            stop_processing = False

            try:
                patient_folder, pseudonym = self._download_request(
                    requests, folder_path
                )

                logger.info("Successfully processed request with ID %d.", request_id)
                stop_processing = process_callback(
                    {
                        "RequestID": request_id,
                        "Pseudonym": pseudonym,
                        "Status": BatchTransferHandler.SUCCESS,
                        "Message": None,
                        "Folder": patient_folder,
                    }
                )
            except Exception as err:
                logger.error(
                    "Error while processing request with ID %d: %s", request_id, err
                )
                stop_processing = process_callback(
                    {
                        "RequestID": request_id,
                        "Pseudonym": None,
                        "Status": BatchTransferHandler.FAILURE,
                        "Message": str(err),
                        "Folder": None,
                    }
                )
            finally:
                # The callback can force to halt the processing and may schedule
                # the processing of the remaining requests sometime later
                if stop_processing and i < len(requests) - 1:
                    return False  # We are not finished yet

                # A customizable timeout (in seconds) between each batch request
                sleep(self.config.batch_timeout)

        return True  # All requests were processed

    def _transfer_to_server(self, requests, callback):
        def _callback(result):
            folder_to_upload = result.pop("Folder")
            if folder_to_upload:
                self.destination.upload_folder(folder_to_upload)
                shutil.rmtree(folder_to_upload)
            return callback(result)

        temp_folder = tempfile.mkdtemp(dir=self.config.cache_folder)
        finished = self._process_requests(requests, temp_folder, _callback)
        shutil.rmtree(temp_folder)
        return finished

    def _transfer_to_folder(self, requests, callback):
        folder_name = f"{self.config.username}_{datetime.now().isoformat()}"
        folder = self.destination / folder_name
        folder.mkdir()

        def _callback(result):
            del result["Folder"]
            return callback(result)

        return self._process_requests(requests, folder, _callback)

    def _transfer_to_archive(self, requests, callback):
        archive_name = f"{self.config.username}_{datetime.now().isoformat()}"
        self._create_archive(archive_name)
        temp_folder = tempfile.mkdtemp(dir=self.config.cache_folder)

        def _callback(result):
            folder_to_add = result.pop("Folder")
            self._add_to_archive(folder_to_add, archive_name)
            shutil.rmtree(folder_to_add)
            return callback(result)

        finished = self._process_requests(requests, temp_folder, _callback)
        shutil.rmtree(temp_folder)
        return finished

    def batch_transfer(self, requests, callback):
        logger.info(
            "Starting to transfer %d requests at %s with config: %s",
            len(requests),
            datetime.now().ctime(),
            self.config,
        )

        if isinstance(self.destination, DicomConnector):
            finished = self._transfer_to_server(requests, callback)
        else:
            assert isinstance(self.destination, Path)
            if self.config.archive_password:
                finished = self._transfer_to_archive(requests, callback)
            else:
                finished = self._transfer_to_folder(requests, callback)

        logger.info(
            "Transfered %d requests at %s with config: %s",
            len(requests),
            datetime.now().ctime(),
            self.config,
        )

        return finished
