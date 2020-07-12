import logging
import os
import shutil
import tempfile
import subprocess
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from main.utils.dicom_transferrer import (
    DicomTransferrerConfig, DicomTransferrer
)
from main.utils.anonymizer import Anonymizer

@dataclass
class BatchTransferrerConfig(DicomTransferrerConfig):
    archive_name: str = None
    trial_protocol_id: str = None
    trial_protocol_name: str = None
    pseudonymize: bool = True
    cache_folder: str = '/tmp'

class BatchTransferrer(DicomTransferrer):
    def __init__(self, config: BatchTransferrerConfig):
        super().__init__(config)
        self.config = config
        self._anonymizer = Anonymizer()
        self.patient_cache = dict()
        self.pseudonym_cache = dict()

    def _modify_dataset(self, pseudonym, ds):
        """Optionally pseudonymize an incoming dataset with the given pseudonym 
        and add the trial ID and name to the DICOM header if specified."""

        if self.config.pseudonymize:
            self._anonymizer.anonymize_dataset(ds, patient_name=pseudonym)

        if self.config.trial_protocol_id:
            ds.ClinicalTrialProtocolID = self.config.trial_protocol_id
        
        if self.config.trial_protocol_name:
            ds.ClinicalTrialProtocolName = self.config.trial_protocol_name

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

    def _batch_process(self, requests, folder_path, callback, cleanup=True):
        """The heart of the batch transferrer which handles each request, download the
        DICOM data, calls a handler to process it and optionally cleans everything up."""

        for request in requests:
            request_id = request['RequestID']

            try:
                patient = self._fetch_patient(request)
                patient_id = patient['PatientID']

                # Only works ok when a provided pseudonym in the Excel file is assigned to the same patient 
                # in the whole file. Never mix provided pseudonym with not filled out pseudonym for the
                # same patient.
                if self.config.pseudonymize:
                    pseudonym = request['Pseudonym']
                    if not pseudonym:
                        pseudonym = self._fetch_pseudonym(patient_id)
                    patient_folder_name = pseudonym
                else:
                    pseudonym = None
                    patient_folder_name = patient_id
                patient_folder_path = os.path.join(folder_path, patient_folder_name)

                if not os.path.exists(patient_folder_path):
                        Path(patient_folder_path).mkdir()

                study_date = request['StudyDate']
                modality = request['Modality']
                study_list = self.find_studies(patient_id, study_date, modality)

                for study in study_list:
                    study_uid = study['StudyInstanceUID']
                    study_date = study['StudyDate']
                    study_time = study['StudyTime']
                    modalities = ','.join(study['Modalities'])
                    study_folder_name = f'{study_date}-{study_time}-{modalities}'
                    study_folder_path = os.path.join(patient_folder_path, study_folder_name)
                    modifier_callback = partial(self._modify_dataset, pseudonym)
                    self.download_study(patient_id, study_uid, study_folder_path,
                            modality, modifier_callback=modifier_callback)

                logging.info(f'Successfully processed request with ID {request_id}.')
                callback({
                    'RequestID': request_id,
                    'Status': DicomTransferrer.SUCCESS,
                    'Message': None,
                    'Folder': patient_folder_path,
                    'Pseudonym': pseudonym
                })
            except Exception as err:
                logging.error(f'Error while processing request with ID {request_id}: {err}')
                callback({
                    'RequestID': request_id,
                    'Status': DicomTransferrer.ERROR,
                    'Message': str(err),
                    'Folder': None,
                    'Pseudonym': None
                })

    def _create_archive(self, archive_password):
        """Create a new archive with just an INDEX.txt file in it."""

        temp_folder_path = tempfile.mkdtemp(dir=self.config.cache_folder)

        readme_path = os.path.join(temp_folder_path, 'INDEX.txt')
        readme_file = open(readme_path, 'w')
        readme_file.write(f'Archive created by {self.config.username} at {datetime.now()}.')
        readme_file.close()

        archive_path = os.path.join(self.config.destination_folder, self.config.archive_name)
        if Path(archive_path).is_file():
            raise Exception(f'Archive ${archive_path} already exists.')

        self._add_to_archive(readme_path, archive_password)

        shutil.rmtree(temp_folder_path)

    def _add_to_archive(self, path_to_add, archive_password):
        """Add a file or folder to an archive. If the archive does not exist 
        it will be created."""

        # TODO catch error like https://stackoverflow.com/a/46098513/166229
        password_option = '-p' + archive_password
        archive_path = os.path.join(self.config.destination_folder, self.config.archive_name + ".7z")
        cmd = ['7z', 'a', password_option, '-mhe=on', '-mx1', '-y', archive_path, path_to_add]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL)
            proc.wait()
            (_, stderr) = proc.communicate()
            if proc.returncode != 0:
                raise Exception('Failed to add path to archive (%s)' % stderr)
        except Exception as err:
            raise Exception('Failure while executing 7zip: %s' % str(err))

    def transfer_to_folder(self, requests, progress_callback, archive_password=None):
        logging.info(f'Starting download of {len(requests)} requests at {datetime.now().ctime()}'
                f'with config: {self.config}')

        add_to_archive = self.config.archive_name and archive_password

        if add_to_archive:
            self._create_archive(archive_password)
            cache_folder_path = tempfile.mkdtemp(dir=self.config.cache_folder)
            destination_folder_path = cache_folder_path
        else:
            destination_folder_path = self.config.destination_folder
            cache_folder_path = None

        def callback(result):
            if add_to_archive and result['Status'] == BatchTransferrer.SUCCESS:
                folder_path = result['Folder']
                self._add_to_archive(folder_path, archive_password)
                # Cleanup when folder is archived
                shutil.rmtree(folder_path)

            progress_callback(result)

        #self._batch_process(requests, cache_folder_path, callback)

        # Cleanup when finished
        if (cache_folder_path):
            shutil.rmtree(cache_folder_path)

        logging.info(f'Finished download of {len(requests)} requests at {datetime.now().ctime()}'
                f'with config: {self.config}')

    def transfer_to_server(self, requests, progress_callback):
        logging.info(f'Starting transfer of {len(requests)} requests at {datetime.now().ctime()}'
                f'with config: {self.config}')

        def handler_callback(result):
            #self.upload_folder(result...)
            pass

        cache_folder_path = tempfile.mkdtemp(dir=self.config.cache_folder)
        #self._batch_process(requests, cache_folder_path, handler_callback)

        logging.info(f'Finished download of {len(requests)} requests at {datetime.now().ctime()}'
                f'with config: {self.config}')
