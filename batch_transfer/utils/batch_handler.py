import logging
import shutil
import tempfile
import subprocess
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from main.utils.dicom_handler import DicomHandler
from main.utils.anonymizer import Anonymizer

class BatchHandler(DicomHandler):

    @dataclass
    class Config(DicomHandler.Config):
        trial_protocol_id: str = None
        trial_protocol_name: str = None
        pseudonymize: bool = True
        cache_folder: str = '/tmp'

    def __init__(self, config: Config):
        super().__init__(config)
        self.config = config
        self._anonymizer = Anonymizer()
        self.patient_cache = dict()
        self.pseudonym_cache = dict()

    def _create_archive(self, archive_name, archive_password):
        """Create a new archive with just an INDEX.txt file in it."""

        temp_folder_path = tempfile.mkdtemp(dir=self.config.cache_folder)

        readme_path = Path(temp_folder_path) / 'INDEX.txt'
        readme_file = open(readme_path, 'w')
        readme_file.write(f'Archive created by {self.config.username} at {datetime.now()}.')
        readme_file.close()

        archive_path = Path(self.config.destination_folder) / archive_name
        if Path(archive_path).is_file():
            raise Exception(f'Archive ${archive_path} already exists.')

        self._add_to_archive(readme_path, archive_name, archive_password)

        shutil.rmtree(temp_folder_path)

    def _add_to_archive(self, path_to_add, archive_name, archive_password):
        """Add a file or folder to an archive. If the archive does not exist 
        it will be created."""

        # TODO catch error like https://stackoverflow.com/a/46098513/166229
        password_option = '-p' + archive_password
        archive_path = Path(self.config.destination_folder) / archive_name + '.7z'
        cmd = ['7z', 'a', password_option, '-mhe=on', '-mx1', '-y', archive_path, path_to_add]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL)
            proc.wait()
            (_, stderr) = proc.communicate()
            if proc.returncode != 0:
                raise Exception('Failed to add path to archive (%s)' % stderr)
        except Exception as err:
            raise Exception('Failure while executing 7zip: %s' % str(err))

    def _fetch_patient(self, request):
        """Fetch the correct patient for this request. Raises an error if there
        are multiple patients for this request."""

        request_id = request['RequestID']

        patient_id = request['PatientID']
        patient_name = request['PatientName']
        patient_birth_date = request['PatientBirthDate']

        patient_key = f'{patient_id}__{patient_name}__{patient_birth_date}'
        if patient_key in self.patient_cache:
            return self.patient_cache[patient_key]

        patients = self.find_patients(patient_id, patient_name, patient_birth_date)
        if len(patients) != 1:
            raise Exception(f'Ambigious patient for request with ID {request_id}.')

        patient = patients[0]
        patient_id = patient['PatientID']
        patient_name = patient['PatientName']
        patient_birth_date = patient['PatientBirthDate']

        patient_key = f'{patient_id}__{patient_name}__{patient_birth_date}'
        self.patient_cache[patient_key] = patient

        return patient

    def _fetch_pseudonym(self, patient_id):
        """Returns a given pseudonym for the specified patient ID or create a new one."""

        pseudonym = self.pseudonym_cache.get(patient_id)
        if not pseudonym:
            pseudonym = self._anonymizer.generate_pseudonym()
            self.pseudonym_cache[patient_id] = pseudonym

        return pseudonym

    def _modify_dataset(self, pseudonym, ds):
        """Optionally pseudonymize an incoming dataset with the given pseudonym 
        and add the trial ID and name to the DICOM header if specified."""

        if self.config.pseudonymize:
            self._anonymizer.anonymize_dataset(ds, patient_name=pseudonym)

        if self.config.trial_protocol_id:
            ds.ClinicalTrialProtocolID = self.config.trial_protocol_id
        
        if self.config.trial_protocol_name:
            ds.ClinicalTrialProtocolName = self.config.trial_protocol_name

    def _batch_process(self, requests, folder_path, process_callback, cleanup=True):
        """The heart of the batch transferrer which handles each request, download the
        DICOM data, calls a handler to process it and optionally cleans everything up."""

        for request in requests:
            request_id = request['RequestID']

            try:
                patient = self._fetch_patient(request)
                patient_id = patient['PatientID']

                # Only works ok when a provided pseudonym in the Excel file is assigned to the same patient 
                # in the whole file. Never mix provided pseudonym with not filled out pseudonym for the
                # same patient. TODO validate that in excel loader
                if self.config.pseudonymize:
                    pseudonym = request['Pseudonym']
                    if not pseudonym:
                        pseudonym = self._fetch_pseudonym(patient_id)
                    patient_folder_name = pseudonym
                else:
                    pseudonym = None
                    patient_folder_name = patient_id

                patient_folder_path = Path(folder_path) / patient_folder_name
                patient_folder_path.mkdir(exist_ok=True)

                study_date = request['StudyDate']
                modality = request['Modality']
                study_list = self.find_studies(patient_id, study_date, modality)

                for study in study_list:
                    study_uid = study['StudyInstanceUID']
                    study_date = study['StudyDate']
                    study_time = study['StudyTime']
                    modalities = ','.join(study['Modalities'])
                    study_folder_name = f'{study_date}-{study_time}-{modalities}'
                    study_folder_path = patient_folder_path / study_folder_name
                    modifier_callback = partial(self._modify_dataset, pseudonym)
                    self.download_study(patient_id, study_uid, study_folder_path,
                            modality, modifier_callback=modifier_callback)

                logging.info(f'Successfully processed request with ID {request_id}.')
                stop_processing = process_callback({
                    'RequestID': request_id,
                    'Status': DicomHandler.SUCCESS,
                    'Message': None,
                    'Folder': patient_folder_path,
                    'Pseudonym': pseudonym
                })
            except Exception as err:
                logging.error(f'Error while processing request with ID {request_id}: {err}')
                stop_processing = process_callback({
                    'RequestID': request_id,
                    'Status': DicomHandler.ERROR,
                    'Message': str(err),
                    'Folder': None,
                    'Pseudonym': None
                })
            finally:
                if stop_processing:
                    break

    def batch_download(self, requests, handler_callback, archive_password=None):
        logging.info(f'Starting download of {len(requests)} requests at {datetime.now().ctime()}'
                f'with config: {self.config}')

        if archive_password:
            # When an archive should be used then download to the cache folder
            # and it to the archive from there
            archive_name = f'{self.config.username}_{datetime.now().isoformat()}'
            self._create_archive(archive_name, archive_password)
            download_path = tempfile.mkdtemp(dir=self.config.cache_folder)
        else:
            # Otherwise download directly to destination folder
            dest_folder_name = f'{self.config.username}_{datetime.now().isoformat()}'
            download_path = Path(self.config.destination_folder) / dest_folder_name
            download_path.mkdir()

        def process_callback(result):
            if archive_password and result['Status'] == DicomHandler.SUCCESS:
                folder_path_to_add = result['Folder']
                self._add_to_archive(folder_path_to_add, archive_name, archive_password)
                # Cleanup when folder was archived
                shutil.rmtree(folder_path_to_add)

            return handler_callback(result)

        self._batch_process(requests, download_path, process_callback)

        # Cleanup the temporary cache folder if an archive was created
        if archive_password:
            shutil.rmtree(download_path)

        logging.info(f'Finished download of {len(requests)} requests at {datetime.now().ctime()}'
                f'with config: {self.config}')

    def batch_transfer(self, requests, handler_callback):
        logging.info(f'Starting transfer of {len(requests)} requests at {datetime.now().ctime()}'
                f'with config: {self.config}')

        def process_callback(result):
            folder_path = result['Folder']
            self.upload_folder(folder_path)
            shutil.rmtree(folder_path)
            return handler_callback(result)

        cache_folder_path = tempfile.mkdtemp(dir=self.config.cache_folder)
        self._batch_process(requests, cache_folder_path, process_callback)

        logging.info(f'Finished download of {len(requests)} requests at {datetime.now().ctime()}'
                f'with config: {self.config}')
